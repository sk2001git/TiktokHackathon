import React, { useEffect, useMemo, useState } from "react";
import { listLegalDocuments, listCriteriaForDocument, uploadProjectDocs, verifyDocset } from "../lib/api";
import { LegalDocMin, Criterion, ComplianceResult } from "../lib/types";
import { Button, Card, Input, Pill, classNames, Tone } from "./ui";

type UserViewProps = {
  userId: string;
};

export function UserView({ userId }: UserViewProps) {
  // Global state for this view
  const [error, setError] = useState<string | null>(null);
  
  // Step 1: Select Law
  const [laws, setLaws] = useState<LegalDocMin[]>([]);
  const [selectedLawId, setSelectedLawId] = useState<string | null>(null);
  const [loadingLaws, setLoadingLaws] = useState(true);

  // Step 2: Upload Docs
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [docSetUid, setDocSetUid] = useState<string | null>(null);

  // Step 3: Select Criterion
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [selectedCriterionId, setSelectedCriterionId] = useState<string | null>(null);
  const [loadingCriteria, setLoadingCriteria] = useState(false);
  const [filterQuery, setFilterQuery] = useState("");

  // Step 4: Verify & Results
  const [topK, setTopK] = useState(5);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<ComplianceResult | null>(null);

  const toast = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  };

  const refreshLaws = async () => {
    setLoadingLaws(true);
    try {
      const res = await listLegalDocuments();
      setLaws(res.data || []);
      if (res.data?.length > 0) {
        handleLawSelection(res.data[0]._id);
      }
    } catch (e: any) {
      toast(`Failed to load legal docs: ${e.message}`);
    } finally {
      setLoadingLaws(false);
    }
  };

  useEffect(() => {
    refreshLaws();
  }, []);

  const handleLawSelection = async (lawId: string) => {
    setSelectedLawId(lawId);
    setSelectedCriterionId(null);
    setVerifyResult(null);
    setLoadingCriteria(true);
    try {
      const crit = await listCriteriaForDocument(lawId);
      setCriteria(crit);
    } catch (e: any) {
      toast(`Failed to load criteria: ${e.message}`);
    } finally {
      setLoadingCriteria(false);
    }
  };

  const handleUpload = async () => {
    if (!userId.trim()) return toast("Please enter a User ID in the header.");
    if (files.length === 0) return toast("Please select at least one file to upload.");
    setUploading(true);
    setVerifyResult(null);
    try {
      const res = await uploadProjectDocs(userId, files);
      setDocSetUid(res.doc_set_uid);
      toast(`Upload successful. Doc Set UID: ${res.doc_set_uid.slice(0, 8)}...`);
    } catch (e: any) {
      toast(`Upload failed: ${e.message}`);
    } finally {
      setUploading(false);
    }
  };
  
  const handleVerify = async () => {
    if (!userId.trim()) return toast("Please enter a User ID.");
    if (!selectedCriterionId) return toast("Please select a criterion to verify.");
    if (!docSetUid) return toast("Please upload your project documents first.");
    setVerifying(true);
    setVerifyResult(null);
    try {
        const res = await verifyDocset(userId, {
            criterion_id: selectedCriterionId,
            doc_set_uid: docSetUid,
            top_k: topK
        });
        setVerifyResult(res);
    } catch (e: any) {
        toast(`Verification failed: ${e.message}`);
    } finally {
        setVerifying(false);
    }
  };
  
  const filteredCriteria = useMemo(() => {
    if (!filterQuery) return criteria;
    return criteria.filter(c => 
      JSON.stringify(c).toLowerCase().includes(filterQuery.toLowerCase())
    );
  }, [criteria, filterQuery]);
  
  const complianceTone: Tone = useMemo(() => {
    const status = verifyResult?.compliance_status?.toUpperCase();
    if (status === 'COMPLIANT') return 'good';
    if (status === 'NON_COMPLIANT') return 'bad';
    return 'warn';
  }, [verifyResult]);


  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
      {/* Left Column: Setup */}
      <div className="lg:col-span-2 space-y-6">
        <Card title="Step 1: Select a Legal Document" subtitle="Choose the regulation to check compliance against.">
          <div className="max-h-60 space-y-2 overflow-auto pr-2">
            {loadingLaws && <p className="text-sm text-slate-500">Loading documents...</p>}
            {laws.map(law => (
              <label key={law._id} className={classNames(
                "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors",
                selectedLawId === law._id ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200" : "border-slate-200 hover:bg-slate-50"
              )}>
                <input
                  type="radio"
                  name="law"
                  className="mt-1"
                  checked={selectedLawId === law._id}
                  onChange={() => handleLawSelection(law._id)}
                />
                <div>
                  <div className="font-medium text-slate-800">{law.law_name || "(Untitled)"}</div>
                  <div className="text-xs text-slate-500">
                    {[law.law_citation, law.law_acronym, law.region].filter(Boolean).join(" • ")}
                  </div>
                </div>
              </label>
            ))}
          </div>
        </Card>
        
        <Card title="Step 2: Upload Project Documents" subtitle="Upload your project files (PDF/TXT) for analysis.">
          <input
            type="file"
            multiple
            accept=".pdf,.txt"
            onChange={(e) => setFiles(Array.from(e.target.files || []))}
            className="block w-full text-sm text-slate-500 file:mr-4 file:rounded-full file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-indigo-700 hover:file:bg-indigo-100"
          />
           <div className="flex items-center justify-between">
            <Button onClick={handleUpload} loading={uploading} disabled={!userId || files.length === 0}>
              Upload {files.length > 0 ? `${files.length} file(s)` : ''}
            </Button>
            {docSetUid && <Pill tone="primary">Doc Set UID: {docSetUid.slice(0, 8)}…</Pill>}
          </div>
        </Card>
      </div>

      {/* Right Column: Action */}
      <div className="lg:col-span-3 space-y-6">
        <Card title="Step 3: Select a Compliance Criterion" subtitle={selectedLawId ? "Pick a requirement to verify from the list below." : "First, select a legal document."}>
          <Input
              placeholder="Filter criteria by keyword…"
              value={filterQuery}
              onChange={e => setFilterQuery(e.target.value)}
              disabled={!selectedLawId || loadingCriteria}
          />
          <div className="max-h-80 overflow-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-slate-100/60 text-xs text-slate-600 backdrop-blur-sm">
                  <tr>
                    <th className="w-12 p-3"></th>
                    <th className="p-3">Requirement Summary</th>
                    <th className="p-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingCriteria && <tr><td colSpan={3} className="p-3 text-center text-slate-500">Loading criteria...</td></tr>}
                  {!loadingCriteria && filteredCriteria.length === 0 && <tr><td colSpan={3} className="p-3 text-center text-slate-500">No criteria found.</td></tr>}
                  {filteredCriteria.map(c => (
                      <tr key={c.criterion_id} className="border-t border-slate-200">
                        <td className="p-3 text-center">
                          <input type="radio" name="criterion" checked={selectedCriterionId === c.criterion_id} onChange={() => setSelectedCriterionId(c.criterion_id)} />
                        </td>
                        <td className="p-3 max-w-md">
                           <p className="font-medium text-slate-800 truncate" title={c.requirement_summary}>{c.requirement_summary}</p>
                           <p className="text-xs text-slate-500 truncate" title={c.section_title}>{c.section_title}</p>
                        </td>
                        <td className="p-3">
                            <Pill>{c.actionable_verb}</Pill>
                        </td>
                      </tr>
                  ))}
                </tbody>
            </table>
          </div>
        </Card>
        
        <Card title="Step 4: Run Verification & See Results" subtitle="Check the selected criterion against your uploaded documents.">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                 <Input
                  type="number"
                  min={1}
                  max={10}
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="sm:col-span-1"
                  aria-label="Top-K Chunks"
                />
                <Button onClick={handleVerify} loading={verifying} disabled={!selectedCriterionId || !docSetUid} className="sm:col-span-2">
                    Run Verification
                </Button>
            </div>
            {verifying && <p className="text-sm text-center text-slate-600">Verifying... This may take a moment.</p>}
            {verifyResult && (
                 <div className="space-y-4 pt-4 border-t border-slate-200">
                     <div className="grid grid-cols-3 gap-4 text-center">
                         <div>
                            <div className="text-xs font-semibold text-slate-500">STATUS</div>
                            <Pill tone={complianceTone}><span className="font-bold">{verifyResult.compliance_status}</span></Pill>
                         </div>
                         <div>
                            <div className="text-xs font-semibold text-slate-500">CONFIDENCE</div>
                            <p className="text-lg font-bold text-slate-800">{(verifyResult.confidence_score * 100).toFixed(1)}%</p>
                         </div>
                         <div>
                            <div className="text-xs font-semibold text-slate-500">REVIEW FLAG</div>
                            <p className="text-lg font-bold text-slate-800">{verifyResult.flag_for_human_review ? 'Yes' : 'No'}</p>
                         </div>
                     </div>
                     <div>
                        <h4 className="text-sm font-semibold text-slate-800">Reasoning</h4>
                        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700 bg-slate-50 rounded-lg p-3">{verifyResult.reasoning}</p>
                     </div>
                     <div>
                        <h4 className="text-sm font-semibold text-slate-800">Supporting Evidence</h4>
                        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700 bg-slate-50 rounded-lg p-3">{verifyResult.supporting_evidence_from_document || "No direct evidence found."}</p>
                     </div>
                 </div>
            )}
        </Card>
      </div>
      {error && (
        <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2">
          <div className="rounded-xl bg-rose-600 px-4 py-3 text-sm font-medium text-white shadow-lg">{error}</div>
        </div>
      )}
    </div>
  );
}