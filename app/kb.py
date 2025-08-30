import json
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from httpx import HTTPStatusError

from .config import settings

def _base_url() -> str:
    return settings.DIFY_BASE_URL.rstrip("/") + "/v1"

class KnowledgeBaseClient:
    def __init__(self, api_key: str, dataset_id: str):
        self.api_key = api_key
        self.dataset_id = dataset_id
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    async def _list_metadata_fields(self) -> List[Dict[str, Any]]:
        url_ds = f"{_base_url()}/datasets/{self.dataset_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url_ds, headers=self.headers)
            try:
                r.raise_for_status()
            except HTTPStatusError as e:
                raise RuntimeError(f"List metadata failed: {e.response.status_code} {e.response.text}") from e
            return (r.json().get("doc_metadata") or [])

    async def _ensure_docset_metadata(self) -> None:
        fields = await self._list_metadata_fields()
        if any((f.get("name") == "doc_set_uid") for f in fields):
            return
        url = f"{_base_url()}/datasets/{self.dataset_id}/metadata"
        payload = {"type": "string", "name": "doc_set_uid"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers={**self.headers, "Content-Type": "application/json"}, json=payload)
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Create metadata failed: {r.status_code} {r.text}")

    async def _tag_document_with_docset(self, document_id: str, doc_set_uid: str) -> Dict[str, Any]:
        await self._ensure_docset_metadata()
        url = f"{_base_url()}/datasets/{self.dataset_id}/documents/metadata"
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
            try:
                r.raise_for_status()
            except HTTPStatusError as e:
                raise RuntimeError(f"Tag metadata failed: {e.response.status_code} {e.response.text}") from e
            return r.json()

    async def upload_file(self, file_path: Path, doc_set_uid: str,
                          indexing_technique: str = "high_quality") -> Dict[str, Any]:
        
        process_rule = {
            "mode": "custom",
            "rules": {
                "pre_processing_rules": [
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False}
                ],
                "segmentation": {
                    "separator": "\n\n\n",
                    "max_tokens": 3800,
                    "chunk_overlap": 200
                }
            }
        }
        url = f"{_base_url()}/datasets/{self.dataset_id}/document/create-by-file"
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            with open(file_path, "rb") as f:
                files = {
                    "file": (file_path.name, f, "application/octet-stream"),
                    "data": (None, json.dumps({"process_rule": process_rule, "indexing_technique": indexing_technique}), 'application/json'),
                }
                r = await client.post(url, headers=self.headers, files=files)
                try:
                    r.raise_for_status()
                except HTTPStatusError as e:
                    raise RuntimeError(f"Upload failed: {e.response.status_code} {e.response.text}") from e
                result = r.json()

        document_id = result["document"]["id"]
        await self._tag_document_with_docset(document_id, doc_set_uid)
        return result

    # --- NEW: Method to delete a document from the knowledge base ---
    async def delete_document(self, document_id: str) -> None:
        """
        Deletes a specific document from the knowledge base dataset.
        """
        url = f"{_base_url()}/datasets/{self.dataset_id}/documents/{document_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.delete(url, headers=self.headers)
            try:
                # This will succeed for 2xx status codes, including 204 No Content
                r.raise_for_status()
            except HTTPStatusError as e:
                raise RuntimeError(
                    f"Delete document failed for document_id '{document_id}': "
                    f"{e.response.status_code} {e.response.text}"
                ) from e
        # No return value is needed for a successful deletion (204)

    async def retrieve(self, query: str, doc_set_uid: str, top_k: int = 5,
                       search_method: str = "hybrid_search",
                       reranking_enable: bool = True,
                       score_threshold_enabled: bool = False,
                       score_threshold: Optional[float] = None) -> Dict[str, Any]:
        url = f"{_base_url()}/datasets/{self.dataset_id}/retrieve"
        retrieval_model: Dict[str, Any] = {
            "search_method": search_method,
            "reranking_enable": reranking_enable,
            "top_k": top_k,
            "score_threshold_enabled": score_threshold_enabled,
            "metadata_filtering_conditions": {
                "logical_operator": "and",
                "conditions": [
                    {"name": "doc_set_uid", "comparison_operator": "is", "value": doc_set_uid}
                ],
            },
        }
        if score_threshold is not None:
            retrieval_model["score_threshold"] = score_threshold
        payload = {"query": query, "retrieval_model": retrieval_model}
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers={**self.headers, "Content-Type": "application/json"}, json=payload)
            try:
                r.raise_for_status()
            except HTTPStatusError as e:
                raise RuntimeError(f"Retrieve failed: {e.response.status_code} {e.response.text}") from e
            return r.json()

kb_client = KnowledgeBaseClient(
    api_key=settings.DIFY_DATASET_API_KEY,
    dataset_id=settings.DIFY_DATASET_ID,
)