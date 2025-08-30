import uuid
import tempfile
import hashlib
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from .models import (
    LegalDocument,
    LawIngestionRequest,
    VerificationRequest,
    Criterion,
    ComplianceResult,
    DocsetVerificationRequest,
    VerificationRun,
)
from .database import db
from .dify_client import dify_client
from .kb import kb_client
from .config import settings


app = FastAPI(
    title="Geo-Regulation Governance API",
    description="MVP for automating geo-regulation compliance using LLM workflows.",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://frontend:5173",  # if you open the site via container hostname
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A constant to define the Dify API query limit, with a small buffer.
DIFY_QUERY_MAX_LENGTH = 249

# ---------- Stage 1: Admin ingest law text -> extract & store ----------

@app.post("/ingest-law/", response_model=LegalDocument, status_code=201)
async def ingest_law_document(law_request: LawIngestionRequest):
    # --- START: DUPLICATE DETECTION based on content hash ---
    content_hash = hashlib.sha256(law_request.law_full_text.encode("utf-8")).hexdigest()
    existing_doc = db.find_legal_document_by_hash(content_hash)
    if existing_doc:
        # Return the existing document; FastAPI will default to a 200 OK status
        return existing_doc
    # --- END: DUPLICATE DETECTION ---
    
    try:
        extracted_criteria: List[Criterion] = await dify_client.run_extraction_workflow(law_request)

        legal_document = LegalDocument(
            law_full_text=law_request.law_full_text,
            law_name=law_request.law_name,
            law_citation=law_request.law_citation,
            law_acronym=law_request.law_acronym,
            region=law_request.region,
            criteria=extracted_criteria or [],
            content_hash=content_hash,  # <-- Store the hash with the new document
        )

        db.insert_legal_document(legal_document)
        return legal_document
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

# 👉 New: list documents for frontend (radio buttons)
@app.get("/legal-documents")
def list_legal_documents_min():
    try:
        return {"data": db.list_legal_documents_min()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 👉 New: list criteria for a given legal doc (populate the user's checklist)
@app.get("/legal-documents/{doc_id}/criteria", response_model=List[Criterion])
def list_criteria_for_document(doc_id: str):
    try:
        crits = db.list_criteria_by_doc_id(doc_id)
        return crits
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------- Stage 2: User uploads project docs -> verify ----------
@app.post("/upload-docs/")
async def upload_documents(
    user_id: str = Query(..., description="External user id or email"),
    files: List[UploadFile] = File(...)
):
    """
    Upload multiple files (PDF/TXT), checking for duplicates based on content hash.
    Server generates doc_set_uid and stores:
      - owner_external_id (user_id)
      - dify document ids
      - filenames
      - file_hashes
    """
    db.upsert_user(external_id=user_id)
    doc_set_uid = str(uuid.uuid4())
    db.create_doc_set(doc_set_uid=doc_set_uid, owner_external_id=user_id, dify_dataset_id=settings.DIFY_DATASET_ID)

    uploaded = []
    skipped_duplicates = [] # <-- Track skipped files
    for f in files:
        suffix = Path(f.filename).suffix.lower()
        if suffix not in (".pdf", ".txt"):
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

        # --- START: DUPLICATE DETECTION LOGIC ---
        file_content = await f.read()
        file_hash = hashlib.sha256(file_content).hexdigest()

        if db.check_if_hash_exists_in_set(doc_set_uid, file_hash):
            skipped_duplicates.append({"name": f.filename, "reason": "Duplicate content detected"})
            continue # Skip to the next file
        # --- END: DUPLICATE DETECTION LOGIC ---

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_content) # Use the content we already read
            tmp_path = Path(tmp.name)

        try:
            result = await kb_client.upload_file(tmp_path, doc_set_uid=doc_set_uid)
            dify_doc_id = result["document"]["id"]
            
            # Pass the hash to the updated database method
            db.add_doc_to_set(doc_set_uid, dify_document_id=dify_doc_id, filename=f.filename, file_hash=file_hash)
            
            uploaded.append({"name": f.filename, "document_id": dify_doc_id})
            db.set_docset_status(doc_set_uid, "indexing")
        except Exception as e:
            db.set_docset_status(doc_set_uid, "error")
            raise HTTPException(status_code=500, detail=f"Failed to upload {f.filename}: {e}")
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    return {"doc_set_uid": doc_set_uid, "uploaded": uploaded, "skipped": skipped_duplicates}

def _make_batches_from_records(records: List[dict], max_chars: int = 80000):
    """
    Greedy-pack retrieved chunks into 1..N batches up to ~max_chars each.
    We include lightweight 'source_id' headers so the verifier can reference them.
    """
    batches, cur, n_chars = [], [], 0
    SEP = "\n\n----- CHUNK -----\n\n"
    for i, rec in enumerate(records):
        seg = (rec.get("segment") or {})
        text = (seg.get("content") or "").strip()
        if not text:
            continue
        header = f"[chunk:{i}]"
        piece = f"{SEP}{header}\n{text}\n"
        if n_chars + len(piece) > max_chars and cur:
            batches.append("".join(cur))
            cur, n_chars = [], 0
        cur.append(piece)
        n_chars += len(piece)
    if cur:
        batches.append("".join(cur))
    return batches


def _compose_query_from_criterion(criterion: Criterion) -> str:
    """
    Composes a search query from a criterion, prioritizing keywords and respecting the Dify API character limit.
    """
    # Prioritize the most specific, keyword-like fields first.
    keyword_parts = [
        criterion.actionable_verb,
        criterion.target_of_action,
    ]
    
    # The summary provides the main context for the search.
    summary = criterion.requirement_summary or ""
    
    # Combine the parts, with keywords at the beginning.
    # The `condition_trigger` is often too long and less useful for retrieval, so it's omitted here.
    full_query = " | ".join([p for p in keyword_parts if p] + [summary])

    # Truncate the final query to ensure it fits within the Dify API's limit.
    return full_query[:DIFY_QUERY_MAX_LENGTH]

def _aggregate_results(per_chunk: List[ComplianceResult]) -> ComplianceResult:
    if not per_chunk:
        return ComplianceResult(
            criterion_id="unknown",
            compliance_status="UNCERTAIN",
            confidence_score=0.0,
            reasoning="No candidate chunks retrieved for verification.",
            supporting_evidence_from_document="",
            flag_for_human_review=True,
        )

    def pick(status: str) -> Optional[ComplianceResult]:
        candidates = [r for r in per_chunk if r.compliance_status.upper() == status]
        return max(candidates, key=lambda r: r.confidence_score) if candidates else None

    best_compliant = pick("COMPLIANT")
    if best_compliant:
        return best_compliant

    best_non = pick("NON_COMPLIANT")
    if best_non:
        return best_non

    return max(per_chunk, key=lambda r: r.confidence_score)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Geo-Governance Compliance API v2"}

@app.get("/users/{user_id}/doc-sets")
def list_user_doc_sets(user_id: str):
    return {"data": [ds.model_dump(by_alias=True) for ds in db.list_doc_sets_for_user(user_id)]}

@app.delete("/users/{user_id}/doc-sets/{doc_set_uid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doc_set(user_id: str, doc_set_uid: str):
    """
    Deletes a document set, including all associated documents from the knowledge base.
    """
    # 1. Verify ownership and retrieve the document set
    doc_set = db.get_doc_set(doc_set_uid, owner_external_id=user_id)
    if not doc_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document set not found for this user."
        )

    # 2. Delete associated documents from the Dify knowledge base
    if doc_set.dify_document_ids:
        for doc_id in doc_set.dify_document_ids:
            try:
                await kb_client.delete_document(doc_id)
            except Exception as e:
                # Log error and continue to ensure we attempt to delete as much as possible
                logging.error(f"Failed to delete document {doc_id} from Dify for doc_set {doc_set_uid}: {e}")

    # 3. Delete the doc_set record from our database
    db.delete_doc_set(doc_set_uid, owner_external_id=user_id)

    # 4. Return HTTP 204 No Content
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.post("/verify-docset/", response_model=ComplianceResult)
async def verify_docset(request: DocsetVerificationRequest, user_id: str = Query(...)):
    ds = db.get_doc_set(request.doc_set_uid, owner_external_id=user_id)
    if not ds:
        raise HTTPException(status_code=404, detail="doc_set_uid not found for this user.")

    criterion = db.get_criterion_by_id(request.criterion_id)
    if not criterion:
        raise HTTPException(status_code=404, detail=f"Criterion '{request.criterion_id}' not found.")

    query = request.query_override or _compose_query_from_criterion(criterion)

    try:
        retrieval = await kb_client.retrieve(
            query=query,
            doc_set_uid=request.doc_set_uid,
            top_k=20,                # more recall
            search_method="hybrid_search",
            reranking_enable=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dify retrieval failed: {e}")

    records = retrieval.get("records", []) or []
    if not records:
        result = ComplianceResult(
            criterion_id=criterion.criterion_id,
            compliance_status="UNCERTAIN",
            confidence_score=0.0,
            reasoning="No relevant chunks retrieved for the given doc_set_uid.",
            supporting_evidence_from_document="",
            flag_for_human_review=True,
        )
        db.record_verification(VerificationRun(
            owner_external_id=user_id, doc_set_uid=request.doc_set_uid,
            criterion_id=criterion.criterion_id, top_k=20, result=result,
        ))
        return result

    # --- NEW: batch the evidence into ~80k char payloads (usually 1–2 batches) ---
    batches = _make_batches_from_records(records, max_chars=80000)

    batch_results: List[ComplianceResult] = []
    for batch_text in batches:
        try:
            llm_output_dict = await dify_client.run_verification_workflow(
                criterion=criterion, document_text=batch_text
            )
            res = ComplianceResult(criterion_id=criterion.criterion_id, **llm_output_dict)
            batch_results.append(res)
        except Exception as e:
            # Skip malformed / failed batch; continue
            logging.warning(f"Verifier batch failed: {e}")
            continue

    if not batch_results:
        result = ComplianceResult(
            criterion_id=criterion.criterion_id,
            compliance_status="UNCERTAIN",
            confidence_score=0.0,
            reasoning="Verifier returned no usable results for any batch.",
            supporting_evidence_from_document="",
            flag_for_human_review=True,
        )
        db.record_verification(VerificationRun(
            owner_external_id=user_id, doc_set_uid=request.doc_set_uid,
            criterion_id=criterion.criterion_id, top_k=20, result=result,
        ))
        return result

    # Prefer any COMPLIANT with highest confidence; else best confidence overall
    def pick(status: str) -> Optional[ComplianceResult]:
        cands = [r for r in batch_results if r.compliance_status.upper() == status]
        return max(cands, key=lambda r: r.confidence_score) if cands else None

    final = pick("COMPLIANT") or max(batch_results, key=lambda r: r.confidence_score)

    db.record_verification(VerificationRun(
        owner_external_id=user_id, doc_set_uid=request.doc_set_uid,
        criterion_id=criterion.criterion_id, top_k=20, result=final,
    ))
    return final
