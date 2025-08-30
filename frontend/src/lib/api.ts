// lib/api.ts
import { IngestLawPayload, VerifyDocsetPayload, LegalDocMin, Criterion, ComplianceResult, UploadResponse, DocSet } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// Generic JSON fetcher
async function apiJson<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  // Handle successful but empty responses (like 204 No Content from DELETE)
  if (res.status === 204) {
    return null as T;
  }

  if (!res.ok) {
    const errorText = await res.text();
    // Try to parse as JSON for more detailed errors from FastAPI
    try {
      const errorJson = JSON.parse(errorText);
      throw new Error(errorJson.detail || "An unknown API error occurred.");
    } catch {
      throw new Error(errorText || "An unknown API error occurred.");
    }
  }
  return res.json();
}

// Stage 1: Ingestion
export const ingestLawDocument = (payload: IngestLawPayload) => {
  return apiJson("/ingest-law/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
};

export const listLegalDocuments = (): Promise<{ data: LegalDocMin[] }> => {
  return apiJson("/legal-documents");
};

export const listCriteriaForDocument = (docId: string): Promise<Criterion[]> => {
  return apiJson(`/legal-documents/${docId}/criteria`);
};

// Stage 2: Upload & Verification
export const uploadProjectDocs = async (userId: string, files: File[]): Promise<UploadResponse> => {
  const formData = new FormData();
  files.forEach(file => formData.append("files", file));

  const res = await fetch(`${API_BASE}/upload-docs/?user_id=${encodeURIComponent(userId)}`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorText = await res.text();
    try {
      const errorJson = JSON.parse(errorText);
      throw new Error(errorJson.detail || "File upload failed.");
    } catch {
      throw new Error(errorText || "File upload failed.");
    }
  }
  return res.json();
};

export const listDocSets = (userId: string): Promise<{ data: DocSet[] }> => {
  return apiJson(`/users/${userId}/doc-sets`);
};

export const deleteDocSet = (userId: string, docSetUid: string): Promise<void> => {
    return apiJson(`/users/${userId}/doc-sets/${docSetUid}`, {
        method: "DELETE",
    });
};

export const verifyDocset = (userId: string, payload: VerifyDocsetPayload): Promise<ComplianceResult> => {
    return apiJson(`/verify-docset/?user_id=${encodeURIComponent(userId)}`, {
        method: "POST",
        body: JSON.stringify(payload)
    });
};