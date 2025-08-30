export type Criterion = {
  criterion_id: string;
  legal_source?: string;
  section_title?: string;
  requirement_summary?: string;
  actionable_verb?: string;
  target_of_action?: string;
  condition_trigger?: string;
  keywords?: string[];
  exception_conditions?: string[];
  penalty_reference?: string | null;
  certainty_score_LLM_extraction?: number;
};

export type LegalDocMin = {
  _id: string;
  law_name?: string | null;
  law_citation?: string | null;
  law_acronym?: string | null;
  region?: string | null;
};

export type ComplianceResult = {
  criterion_id: string;
  compliance_status: string;
  confidence_score: number;
  reasoning: string;
  supporting_evidence_from_document: string;
  flag_for_human_review: boolean;
};

export type IngestLawPayload = {
  law_full_text: string;
  law_name: string | null;
  law_citation: string | null;
  law_acronym: string | null;
  region: string | null;
};

export type VerifyDocsetPayload = {
  criterion_id: string;
  doc_set_uid: string;
  top_k: number;
  query_override?: string | null;
};

export type UploadResponse = {
  doc_set_uid: string;
  uploaded: { name: string; document_id: string }[];
};