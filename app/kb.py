# kb.py
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx

from .config import settings

DIFY_BASE_URL = "https://api.dify.ai/v1"


class KnowledgeBaseClient:
    """
    Thin client around Dify Knowledge (Datasets) API.
    - Ensures custom metadata field `doc_set_uid` exists.
    - Uploads file/text and tags the document with `doc_set_uid`.
    - Supports filtered retrieval against a given doc_set_uid.
    """

    def __init__(self, api_key: str, dataset_id: str):
        self.api_key = api_key
        self.dataset_id = dataset_id
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    # --------- Metadata helpers ---------

    async def _list_metadata_fields(self) -> List[Dict[str, Any]]:
        # No official list endpoint in some editions; best-effort via dataset details.
        try:
            url_ds = f"{DIFY_BASE_URL}/datasets/{self.dataset_id}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url_ds, headers=self.headers)
                r.raise_for_status()
                ds = r.json()
            return ds.get("doc_metadata", []) or []
        except Exception:
            return []

    async def _ensure_docset_metadata(self) -> None:
        """Create metadata field `doc_set_uid` if it doesn't exist."""
        fields = await self._list_metadata_fields()
        if any((f.get("name") == "doc_set_uid") for f in fields):
            return

        url = f"{DIFY_BASE_URL}/datasets/{self.dataset_id}/metadata"
        payload = {"type": "string", "name": "doc_set_uid"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers={**self.headers, "Content-Type": "application/json"}, json=payload)
            if r.status_code not in (200, 201):
                # If it already exists or your deployment handles this differently, ignore.
                try:
                    r.raise_for_status()
                except Exception:
                    pass

    async def _tag_document_with_docset(self, document_id: str, doc_set_uid: str) -> Dict[str, Any]:
        """Attach metadata doc_set_uid to a document."""
        await self._ensure_docset_metadata()
        url = f"{DIFY_BASE_URL}/datasets/{self.dataset_id}/documents/metadata"
        payload = {
            "operation_data": [
                {
                    "document_id": document_id,
                    "metadata_list": [
                        {"id": "doc_set_uid", "value": doc_set_uid, "name": "doc_set_uid"}
                    ],
                }
            ]
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers={**self.headers, "Content-Type": "application/json"}, json=payload)
            r.raise_for_status()
            return r.json()

    # --------- Upload ---------

    async def upload_file(
        self,
        file_path: Path,
        doc_set_uid: str,
        indexing_technique: str = "high_quality",
        process_rule: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload a PDF/TXT file into the dataset and tag with doc_set_uid.
        """
        if process_rule is None:
            process_rule = {"mode": "automatic"}

        url = f"{DIFY_BASE_URL}/datasets/{self.dataset_id}/document/create-by-file"
        data_payload = {
            "indexing_technique": indexing_technique,
            "process_rule": process_rule,
        }

        # Properly close the file handle after the request
        async with httpx.AsyncClient(timeout=300.0) as client:
            with open(file_path, "rb") as f:
                files = {
                    "file": (file_path.name, f, "application/octet-stream"),
                    "data": (None, json.dumps(data_payload), "text/plain"),
                }
                resp = await client.post(url, headers=self.headers, files=files)
                resp.raise_for_status()
                result = resp.json()

        document_id = result["document"]["id"]
        await self._tag_document_with_docset(document_id, doc_set_uid)
        return result

    async def upload_text(
        self,
        name: str,
        text: str,
        doc_set_uid: str,
        indexing_technique: str = "high_quality",
        process_rule: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload raw text as a document and tag with doc_set_uid.
        """
        if process_rule is None:
            process_rule = {"mode": "automatic"}

        url = f"{DIFY_BASE_URL}/datasets/{self.dataset_id}/document/create-by-text"
        payload = {
            "name": name,
            "text": text,
            "indexing_technique": indexing_technique,
            "process_rule": process_rule,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers={**self.headers, "Content-Type": "application/json"}, json=payload)
            resp.raise_for_status()
            result = resp.json()

        document_id = result["document"]["id"]
        await self._tag_document_with_docset(document_id, doc_set_uid)
        return result

    # --------- Retrieval (isolated by doc_set_uid) ---------

    async def retrieve(
        self,
        query: str,
        doc_set_uid: str,
        top_k: int = 5,
        search_method: str = "semantic_search",
        reranking_enable: bool = False,
        score_threshold_enabled: bool = False,
        score_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve top-k relevant chunks from THIS dataset, filtered by doc_set_uid.
        """
        url = f"{DIFY_BASE_URL}/datasets/{self.dataset_id}/retrieve"

        retrieval_model: Dict[str, Any] = {
            "search_method": search_method,
            "reranking_enable": reranking_enable,
            "top_k": top_k,
            "score_threshold_enabled": score_threshold_enabled,
            "metadata_filtering_conditions": {
                "logical_operator": "and",
                "conditions": [
                    {
                        "name": "doc_set_uid",
                        "comparison_operator": "is",
                        "value": doc_set_uid,
                    }
                ],
            },
        }
        if score_threshold is not None:
            retrieval_model["score_threshold"] = score_threshold

        payload = {"query": query, "retrieval_model": retrieval_model}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers={**self.headers, "Content-Type": "application/json"}, json=payload)
            resp.raise_for_status()
            return resp.json()


# Singleton instance (configure these in your settings)
kb_client = KnowledgeBaseClient(
    api_key=settings.DIFY_KB_API_KEY,
    dataset_id=settings.DIFY_DATASET_ID,  # e.g. "4661a5a0-fdc1-48f7-b1a9-5a3c420bf239"
)
