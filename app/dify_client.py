# dify_client.py
import json
import re
import hashlib
from typing import List, Dict, Any
import httpx

from .config import settings
from .models import Criterion, ComplianceResult, LawIngestionRequest
from .chunker import chunk_legal_text

class ThinkTagCleaner:
    """Remove <think>...</think> blocks from LLM output."""
    _RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)

    @classmethod
    def clean(cls, text: str) -> str:
        return cls._RE.sub("", text).strip()


class CodeFenceUnwrapper:
    """Unwrap the first ```...``` or ```json...``` fenced block if present."""
    _RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

    @classmethod
    def unwrap(cls, text: str) -> str:
        m = cls._RE.search(text)
        return m.group(1).strip() if m else text.strip()
    

class DifyClient:
    def __init__(self, extract_key: str, verify_key: str, base_url: str):
        self.extract_key = extract_key
        self.verify_key = verify_key
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def _headers(api_key: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async def _run_workflow(self, api_key: str, payload: Dict[str, Any]) -> Any:
        url = f"{self.base_url}/workflows/run"
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(url, headers=self._headers(api_key), json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                body = e.response.text if e.response is not None else str(e)
                raise RuntimeError(f"Dify HTTP error: {body}") from e
            except httpx.RequestError as e:
                raise RuntimeError(f"Dify request failed: {e}") from e

        try:
            result = resp.json()
        except ValueError:
            raise RuntimeError(f"Dify returned non-JSON response: {resp.text}")

        outputs = (result.get("data") or {}).get("outputs") or {}
        output_text = outputs.get("text")

        # Some flows may return structured dict/list directly in outputs; allow that.
        if output_text is None and isinstance(outputs, (dict, list)):
            return outputs

        if not output_text:
            raise RuntimeError("Dify workflow did not return any 'outputs.text'.")

        # 1) Remove <think> blocks.
        cleaned = ThinkTagCleaner.clean(output_text)
        # 2) Unwrap ```json ... ``` fences if present.
        cleaned = CodeFenceUnwrapper.unwrap(cleaned)

        # 3) Single source of truth: json.loads() or error.
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                "Failed to parse Dify outputs.text as JSON after removing <think> and unwrapping code fences.\n"
                f"Cleaned text was:\n{cleaned}"
            ) from e



    async def run_extraction_workflow(self, law_request: LawIngestionRequest) -> List[Criterion]:
        all_criteria: List[Criterion] = []
        chunks = chunk_legal_text(law_request.law_full_text)

        for chunk in chunks:
            payload = {
                "inputs": {
                    "legalText": chunk["text"],
                    "legalTitle": law_request.law_name or "Unknown Title",
                },
                "response_mode": "blocking",
                "user": "hackathon-user-extractor",
            }
            data = await self._run_workflow(self.extract_key, payload)

            # 🔧 Normalize Dify shapes: list OR {criteria:[...]} OR {items:[...]}
            if isinstance(data, dict):
                if isinstance(data.get("criteria"), list):
                    data = data["criteria"]
                elif isinstance(data.get("items"), list):
                    data = data["items"]
                else:
                    data = []

            if not isinstance(data, list):
                raise RuntimeError(f"Extraction workflow expected a list, got: {type(data).__name__}")

            if not data:
                continue

            try:
                crits = [Criterion(**item) for item in data]
            except Exception:
                raise RuntimeError(f"Extraction result did not match Criterion schema: {data}")

            # Ensure criterion_id exists and is stable
            for c in crits:
                if not getattr(c, "criterion_id", None):
                    digest = hashlib.sha1(
                        (chunk["section_id"] + str(chunk["chunk_index"]) + chunk["text"]).encode("utf-8")
                    ).hexdigest()[:16]
                    c.criterion_id = f"{chunk['section_id']}-{chunk['chunk_index']}-{digest}"

            all_criteria.extend(crits)

        return all_criteria

    async def run_verification_workflow(self, criterion: Criterion, document_text: str) -> ComplianceResult:
        payload = {
            "inputs": {
                "criteria": criterion.model_dump_json(),
                "content": document_text,
            },
            "response_mode": "blocking",
            "user": "hackathon-user-verifier",
        }
        data = await self._run_workflow(self.verify_key, payload)
        if not isinstance(data, dict):
            raise RuntimeError(f"Verification workflow expected an object, got: {type(data).__name__}")
        try:
            return ComplianceResult(**data)
        except Exception as e:
            raise RuntimeError(f"Verification result did not match ComplianceResult schema: {data}") from e

dify_client = DifyClient(
    extract_key=getattr(settings, "DIFY_EXTRACT_API_KEY", None) or settings.DIFY_API_KEY,
    verify_key=getattr(settings, "DIFY_VERIFY_API_KEY", None) or settings.DIFY_API_KEY,
    base_url=settings.DIFY_BASE_URL,
)
