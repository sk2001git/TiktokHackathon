# database.py
from pymongo import MongoClient, ReturnDocument
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

from .config import settings
from .models import LegalDocument, Criterion, User, DocSet, VerificationRun

class Database:
    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client.geogovernance
        self.collection = self.db.legal_documents
        self.users = self.db.users
        self.doc_sets = self.db.doc_sets
        self.verifications = self.db.verification_runs

    # --- existing ---
    def insert_legal_document(self, doc: LegalDocument):
        return self.collection.insert_one(doc.model_dump(by_alias=True))

    def list_legal_documents_min(self) -> List[dict]:
        cursor = self.collection.find({}, {
            "_id": 1, "law_name": 1, "law_citation": 1, "law_acronym": 1, "region": 1,
        }).sort([("_id", -1)])
        return [{**d, "_id": str(d["_id"])} for d in cursor]

    def list_criteria_by_doc_id(self, doc_id: str) -> List[Criterion]:
        doc = self.collection.find_one({"_id": ObjectId(doc_id)})
        if not doc:
            return []
        return [Criterion(**c) for c in (doc.get("criteria") or [])]

    def get_criterion_by_id(self, criterion_id: str) -> Optional[Criterion]:
        pipeline = [
            {"$match": {"criteria.criterion_id": criterion_id}},
            {"$unwind": "$criteria"},
            {"$match": {"criteria.criterion_id": criterion_id}},
            {"$replaceRoot": {"newRoot": "$criteria"}}
        ]
        result = list(self.collection.aggregate(pipeline))
        if result:
            return Criterion(**result[0])
        return None

    # --- users ---
    def upsert_user(self, external_id: str, display_name: Optional[str] = None) -> User:
        doc = self.users.find_one_and_update(
            {"external_id": external_id},
            {"$setOnInsert": {"external_id": external_id, "display_name": display_name, "created_at": datetime.utcnow()}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        doc["_id"] = str(doc["_id"])
        return User(**doc)

    def get_user_by_external_id(self, external_id: str) -> Optional[User]:
        doc = self.users.find_one({"external_id": external_id})
        return User(**{**doc, "_id": str(doc["_id"])}) if doc else None

    # --- doc sets ---
    def create_doc_set(self, doc_set_uid: str, owner_external_id: str, dify_dataset_id: str) -> DocSet:
        payload = DocSet(
            doc_set_uid=doc_set_uid,
            owner_external_id=owner_external_id,
            dify_dataset_id=dify_dataset_id,
            status="queued",
        ).model_dump(by_alias=True)
        self.doc_sets.insert_one(payload)
        payload["_id"] = str(payload["_id"])
        return DocSet(**payload)

    def add_doc_to_set(self, doc_set_uid: str, dify_document_id: str, filename: str):
        self.doc_sets.update_one(
            {"doc_set_uid": doc_set_uid},
            {"$push": {"dify_document_ids": dify_document_id, "filenames": filename},
             "$set": {"updated_at": datetime.utcnow()}}
        )

    def set_docset_status(self, doc_set_uid: str, status: str):
        self.doc_sets.update_one(
            {"doc_set_uid": doc_set_uid},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}}
        )

    def get_doc_set(self, doc_set_uid: str, owner_external_id: Optional[str] = None) -> Optional[DocSet]:
        q = {"doc_set_uid": doc_set_uid}
        if owner_external_id:
            q["owner_external_id"] = owner_external_id
        doc = self.doc_sets.find_one(q)
        return DocSet(**{**doc, "_id": str(doc["_id"])}) if doc else None

    def list_doc_sets_for_user(self, owner_external_id: str) -> List[DocSet]:
        cursor = self.doc_sets.find({"owner_external_id": owner_external_id}).sort([("updated_at", -1)])
        items = []
        for d in cursor:
            d["_id"] = str(d["_id"])
            items.append(DocSet(**d))
        return items

    # --- verification runs (optional audit) ---
    def record_verification(self, vr: VerificationRun) -> str:
        payload = vr.model_dump(by_alias=True)
        res = self.verifications.insert_one(payload)
        return str(res.inserted_id)

db = Database()
