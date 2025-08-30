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

    def insert_legal_document(self, doc: LegalDocument):
        payload = doc.model_dump(by_alias=True)
        payload['_id'] = doc.id
        
        return self.collection.insert_one(payload)

    def find_legal_document_by_hash(self, content_hash: str) -> Optional[LegalDocument]:
        """Finds a legal document by its content hash to prevent duplicates."""
        doc = self.collection.find_one({"content_hash": content_hash})
        if doc:
            # Ensure the _id is converted to a string for Pydantic model hydration
            doc["_id"] = str(doc["_id"])
            return LegalDocument(**doc)
        return None

    def list_legal_documents_min(self) -> List[dict]:
        cursor = self.collection.find({}, {
            "_id": 1, "law_name": 1, "law_citation": 1, "law_acronym": 1, "region": 1,
        }).sort([("_id", -1)])
        return [{**d, "_id": str(d["_id"])} for d in cursor]

    def list_criteria_by_doc_id(self, doc_id: str) -> List[dict]:
        doc = self.collection.find_one({"_id": ObjectId(doc_id)})
        if not doc:
            return []
        return doc.get("criteria") or []

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

    def delete_doc_set(self, doc_set_uid: str, owner_external_id: str) -> int:
        """Deletes a doc set record if it belongs to the specified user."""
        result = self.doc_sets.delete_one({
            "doc_set_uid": doc_set_uid,
            "owner_external_id": owner_external_id
        })
        return result.deleted_count

    def record_verification(self, vr: VerificationRun) -> str:
        payload = vr.model_dump(by_alias=True)
        res = self.verifications.insert_one(payload)
        return str(res.inserted_id)
    
    def add_doc_to_set(self, doc_set_uid: str, dify_document_id: str, filename: str, file_hash: str):
        self.doc_sets.update_one(
            {"doc_set_uid": doc_set_uid},
            {
                "$push": {
                    "dify_document_ids": dify_document_id,
                    "filenames": filename,
                    "file_hashes": file_hash
                },
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

    def check_if_hash_exists_in_set(self, doc_set_uid: str, file_hash: str) -> bool:
        """Checks if a file with the given hash already exists in the doc set."""
        count = self.doc_sets.count_documents({
            "doc_set_uid": doc_set_uid,
            "file_hashes": file_hash
        })
        return count > 0

db = Database()