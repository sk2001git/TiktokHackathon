# main.py
import uuid
import tempfile
import hashlib
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
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

# ---------- Stage 1: Admin ingest law text -> extract & store ----------

@app.post("/ingest-law/", response_model=LegalDocument, status_code=201)
async def ingest_law_document(law_request: LawIngestionRequest):
    try:
        extracted_criteria: List[Criterion] = await dify_client.run_extraction_workflow(law_request)

        legal_document = LegalDocument(
            law_full_text=law_request.law_full_text,
            law_name=law_request.law_name,
            law_citation=law_request.law_citation,
            law_acronym=law_request.law_acronym,
            region=law_request.region,
            criteria=extracted_criteria or [],
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

def _compose_query_from_criterion(criterion: Criterion) -> str:
    parts = [
        criterion.requirement_summary,
        criterion.actionable_verb,
        criterion.target_of_action,
        criterion.condition_trigger,
    ]
    return " | ".join([p for p in parts if p])

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

@app.post("/verify-docset/", response_model=ComplianceResult)
async def verify_docset(request: DocsetVerificationRequest, user_id: str = Query(...)):
    # Ensure doc_set belongs to this user (basic isolation)
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
            top_k=10, # Retrieve top 10 relevant chunks
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dify retrieval failed: {e}")

    records = retrieval.get("records", []) or []
    if not records:
        result = ComplianceResult(
            criterion_id=criterion.criterion_id,
            compliance_status="UNCERTAIN",
            confidence_score=0.0,
            reasoning="No relevant chunks retrieved from the knowledge base for the given doc_set_uid.",
            supporting_evidence_from_document="",
            flag_for_human_review=True,
        )
        # optional audit
        db.record_verification(VerificationRun(
            owner_external_id=user_id,
            doc_set_uid=request.doc_set_uid,
            criterion_id=criterion.criterion_id,
            top_k=10,
            result=result,
        ))
        return result

    per_chunk_results: List[ComplianceResult] = []
    for rec in records:
        seg = (rec.get("segment") or {})
        chunk_text = seg.get("content") or ""
        if not chunk_text.strip():
            continue
        try:
            res = await dify_client.run_verification_workflow(criterion=criterion, document_text=chunk_text)

            # "First compliant wins" logic: If a compliant result is found, we are done.
            if res.compliance_status.upper() == "COMPLIANT":
                final_result = res
                final_result.criterion_id = criterion.criterion_id # Ensure ID is set

                # Record this successful verification and return immediately
                db.record_verification(VerificationRun(
                    owner_external_id=user_id,
                    doc_set_uid=request.doc_set_uid,
                    criterion_id=criterion.criterion_id,
                    top_k=10, # The attempted k value
                    result=final_result,
                ))
                return final_result

            per_chunk_results.append(res)
        except Exception:
            # If a single chunk fails verification, we skip it and continue
            # This makes the process more resilient
            continue

    # If the loop completes without finding a "COMPLIANT" result,
    # aggregate the non-compliant/uncertain results to find the best one.
    final = _aggregate_results(per_chunk_results)
    final.criterion_id = criterion.criterion_id

    # Record the final aggregated (non-compliant) result in the audit log
    db.record_verification(VerificationRun(
        owner_external_id=user_id,
        doc_set_uid=request.doc_set_uid,
        criterion_id=criterion.criterion_id,
        top_k=10,
        result=final,
    ))
    return final