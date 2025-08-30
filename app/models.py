# app/models.py

from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator
from pydantic.functional_serializers import PlainSerializer


# ---------- ObjectId type for Pydantic v2 ----------

ObjectIdType = Annotated[
    ObjectId,
    BeforeValidator(
        lambda v: (
            ObjectId(v)
            if isinstance(v, str) and ObjectId.is_valid(v)
            else v
        )
    ),
    PlainSerializer(lambda v: str(v), return_type=str),
]


# ---------- Schemas ----------

class Criterion(BaseModel):
    # --- FIX: Made fields that might be missing from LLM extraction Optional ---
    criterion_id: str
    requirement_summary: str
    actionable_verb: str
    target_of_action: str

    # These fields are very likely to be missing in some cases.
    legal_source: Optional[str] = None
    section_title: Optional[str] = None
    condition_trigger: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    exception_conditions: List[str] = Field(default_factory=list)
    penalty_reference: Optional[str] = None
    certainty_score_LLM_extraction: Optional[float] = None


class ComplianceResult(BaseModel):
    criterion_id: str
    compliance_status: str
    confidence_score: float
    reasoning: str
    supporting_evidence_from_document: str
    flag_for_human_review: bool


class LawIngestionRequest(BaseModel):
    law_full_text: str
    law_name: Optional[str] = None
    law_citation: Optional[str] = None
    law_acronym: Optional[str] = None
    region: Optional[str] = None


class LegalDocument(BaseModel):
    id: ObjectIdType = Field(default_factory=ObjectId, alias="_id")
    law_full_text: str
    law_name: Optional[str] = None
    law_citation: Optional[str] = None
    law_acronym: Optional[str] = None
    region: Optional[str] = None
    criteria: List[Criterion] = Field(default_factory=list)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class VerificationRequest(BaseModel):
    criterion_id: str
    document_for_review: str


class DocsetVerificationRequest(BaseModel):
    criterion_id: str
    doc_set_uid: str
    top_k: int = 5
    query_override: Optional[str] = None


class User(BaseModel):
    id: ObjectIdType = Field(default_factory=ObjectId, alias="_id")
    external_id: str
    display_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class DocSet(BaseModel):
    id: ObjectIdType = Field(default_factory=ObjectId, alias="_id")
    doc_set_uid: str
    owner_external_id: str
    dify_dataset_id: str
    dify_document_ids: List[str] = Field(default_factory=list)
    filenames: List[str] = Field(default_factory=list)
    file_hashes: List[str] = Field(default_factory=list)
    status: str = "queued"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class VerificationRun(BaseModel):
    id: ObjectIdType = Field(default_factory=ObjectId, alias="_id")
    owner_external_id: str
    doc_set_uid: str
    criterion_id: str
    top_k: int
    result: ComplianceResult
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )