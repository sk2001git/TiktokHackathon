// components/UserView.tsx
import React, { useEffect, useMemo, useState } from "react";
import { listLegalDocuments, listCriteriaForDocument, uploadProjectDocs, verifyDocset, listDocSets, deleteDocSet } from "../lib/api";
import { LegalDocMin, Criterion, ComplianceResult, DocSet } from "../lib/types";
import { Button, Card, Input, Pill, classNames, Tone } from "./ui";

type UserViewProps = {
  userId: string;
};

type VerificationResults = Record<string, ComplianceResult & { loading?: boolean }>;

// A simple trash icon component to be used locally
const TrashIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
      <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.58.22-2.365.468a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.023 2.5.067V3.75a1.25 1.25 0 10-2.5 0v.317A40.155 40.155 0 0110 4z" clipRule="evenodd" />
    </svg>
);

export function UserView({ userId }: UserViewProps) {
  const [error, setError] = useState<string | null>(null);
  
  // --- State for Law Selection ---
  const [laws, setLaws] = useState<LegalDocMin[]>([]);
  const [selectedLawId, setSelectedLawId] = useState<string | null>(null);
  const [loadingLaws, setLoadingLaws] = useState(true);

  // --- State for Document Upload & Selection---
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [docSets, setDocSets] = useState<DocSet[]>([]);
  const [selectedDocSetUid, setSelectedDocSetUid] = useState<string | null>(null);
  const [loadingDocSets, setLoadingDocSets] = useState(false);

  // --- State for Criteria & Results ---
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [selectedCriterionIds, setSelectedCriterionIds] = useState<string[]>([]);
  const [loadingCriteria, setLoadingCriteria] = useState(false);
  const [filterQuery, setFilterQuery] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verificationResults, setVerificationResults] = useState<VerificationResults>({});
  
  const [expandedCriterionId, setExpandedCriterionId] = useState<string | null>(null);

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
  
  const refreshDocSets = async () => {
    if (!userId) {
      setDocSets([]);
      return;
    }
    setLoadingDocSets(true);
    try {
      const res = await listDocSets(userId);
      setDocSets(res.data || []);
    } catch (e: any) {
      toast(`Failed to load document sets: ${e.message}`);
    } finally {
      setLoadingDocSets(false);
    }
  };

  useEffect(() => {
    refreshLaws();
  }, []);

  useEffect(() => {
    if (userId) {
      refreshDocSets();
    }
  }, [userId]);

  const handleLawSelection = async (lawId: string) => {
    setSelectedLawId(lawId);
    setSelectedCriterionIds([]);
    setVerificationResults({});
    setExpandedCriterionId(null);
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
    setVerificationResults({});
    setExpandedCriterionId(null);
    try {
      const res = await uploadProjectDocs(userId, files);
      setSelectedDocSetUid(res.doc_set_uid);
      toast(`Upload successful. Doc Set UID: ${res.doc_set_uid.slice(0, 8)}...`);
      await refreshDocSets();
    } catch (e: any) {
      toast(`Upload failed: ${e.message}`);
    } finally {
      setUploading(false);
    }
  };
  
  const handleDeleteDocSet = async (docSetUidToDelete: string) => {
    if (!window.confirm("Are you sure you want to delete this document set? This action cannot be undone.")) {
        return;
    }
    try {
        await deleteDocSet(userId, docSetUidToDelete);
        toast("Document set deleted successfully.");
        // If the deleted set was the selected one, unselect it
        if (selectedDocSetUid === docSetUidToDelete) {
            setSelectedDocSetUid(null);
        }
        await refreshDocSets(); // Refresh the list from the server
    } catch (e: any) {
        toast(`Failed to delete document set: ${e.message}`);
    }
  };

  const handleVerify = async () => {
    if (!userId.trim()) return toast("Please enter a User ID.");
    if (selectedCriterionIds.length === 0) return toast("Please select at least one criterion to verify.");
    if (!selectedDocSetUid) return toast("Please select a document set first.");
    
    setVerifying(true);
    setExpandedCriterionId(null);

    const initialResults: VerificationResults = { ...verificationResults };
    selectedCriterionIds.forEach(id => {
      initialResults[id] = { ...criteria.find(c => c.criterion_id === id)!, loading: true } as any;
    });
    setVerificationResults(initialResults);

    const verificationPromises = selectedCriterionIds.map(criterionId => 
      verifyDocset(userId, {
        criterion_id: criterionId,
        doc_set_uid: selectedDocSetUid,
        top_k: 10
      }).then(result => ({ criterionId, result }))
      .catch(error => ({ criterionId, error }))
    );

    const responses = await Promise.all(verificationPromises);
    
    setVerificationResults(prev => {
        const newResults = { ...prev };
        responses.forEach(({ criterionId, result, error }) => {
            if (result) {
                newResults[criterionId] = { ...result, loading: false };
            }
            if (error) {
                toast(`Verification for ${criterionId.slice(0,8)}... failed: ${error.message}`);
                newResults[criterionId] = { ...prev[criterionId], compliance_status: 'ERROR', loading: false };
            }
        });
        return newResults;
    });

    setVerifying(false);
  };
  
  const filteredCriteria = useMemo(() => {
    if (!filterQuery) return criteria;
    return criteria.filter(c => 
      JSON.stringify(c).toLowerCase().includes(filterQuery.toLowerCase())
    );
  }, [criteria, filterQuery]);

  const handleCriterionToggle = (criterionId: string) => {
    setSelectedCriterionIds(prev => 
      prev.includes(criterionId) 
        ? prev.filter(id => id !== criterionId)
        : [...prev, criterionId]
    );
  };
  
  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedCriterionIds(filteredCriteria.map(c => c.criterion_id));
    } else {
      setSelectedCriterionIds([]);
    }
  };

  const handleRowClick = (criterionId: string) => {
    if (!verificationResults[criterionId] || verificationResults[criterionId].loading) return;
    setExpandedCriterionId(prev => (prev === criterionId ? null : criterionId));
  };
  
  const getComplianceTone = (status?: string): Tone => {
    const s = status?.toUpperCase();
    if (s === 'COMPLIANT') return 'good';
    if (s === 'NON_COMPLIANT' || s === 'ERROR') return 'bad';
    return 'warn';
  };

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
        
        <Card title="Step 2: Select or Upload Project Documents" subtitle="Choose an existing set or upload new files.">
            <div className="space-y-4">
                <div>
                    <h3 className="text-sm font-medium text-slate-600">Existing Document Sets</h3>
                    <div className="max-h-40 space-y-2 overflow-auto rounded-lg border border-slate-200 p-2 mt-1">
                        {loadingDocSets && <p className="text-sm text-slate-500">Loading sets...</p>}
                        {!loadingDocSets && docSets.length === 0 && <p className="text-sm text-slate-500">No document sets found.</p>}
                        {docSets.map(ds => (
                            <div key={ds.doc_set_uid} className="flex items-center gap-2">
                                <label className={classNames(
                                    "flex-grow flex cursor-pointer items-start gap-3 rounded-lg border p-2 transition-colors",
                                    selectedDocSetUid === ds.doc_set_uid ? "border-indigo-500 bg-indigo-50" : "border-slate-200 hover:bg-slate-50"
                                )}>
                                    <input
                                        type="radio"
                                        name="docSet"
                                        className="mt-1"
                                        checked={selectedDocSetUid === ds.doc_set_uid}
                                        onChange={() => setSelectedDocSetUid(ds.doc_set_uid)}
                                    />
                                    <div>
                                        <div className="font-mono text-xs font-medium text-slate-700">
                                            {ds.doc_set_uid.slice(0, 8)}...
                                        </div>
                                        <div className="text-xs text-slate-500" title={ds.filenames.join(', ')}>
                                            {ds.filenames.length} file(s)
                                        </div>
                                    </div>
                                </label>
                                <button
                                    onClick={(e) => {
                                      e.stopPropagation(); // Prevent the label from being triggered
                                      handleDeleteDocSet(ds.doc_set_uid);
                                    }}
                                    className="p-2 text-slate-400 hover:text-rose-600 rounded-full hover:bg-rose-50 transition-colors"
                                    title="Delete document set"
                                >
                                    <TrashIcon />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="relative">
                    <div className="absolute inset-0 flex items-center" aria-hidden="true">
                        <div className="w-full border-t border-slate-300" />
                    </div>
                    <div className="relative flex justify-center">
                        <span className="bg-white px-2 text-sm text-slate-500">OR</span>
                    </div>
                </div>

                <div>
                    <h3 className="text-sm font-medium text-slate-600">Upload a New Set</h3>
                    <input
                        type="file"
                        multiple
                        accept=".pdf,.txt"
                        onChange={(e) => setFiles(Array.from(e.target.files || []))}
                        className="mt-2 block w-full text-sm text-slate-500 file:mr-4 file:rounded-full file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-indigo-700 hover:file:bg-indigo-100"
                    />
                    <div className="mt-4 flex items-center justify-between">
                        <Button onClick={handleUpload} loading={uploading} disabled={!userId || files.length === 0}>
                            Upload {files.length > 0 ? `${files.length} file(s)` : ''}
                        </Button>
                    </div>
                </div>
            </div>
        </Card>

        <Card title="Step 3: Run Verification" subtitle="Check the selected criteria against your chosen documents.">
            <Button onClick={handleVerify} loading={verifying} disabled={selectedCriterionIds.length === 0 || !selectedDocSetUid} className="w-full">
                Run Verification on {selectedCriterionIds.length} item(s)
            </Button>
        </Card>
      </div>

      {/* Right Column: Criteria and Results */}
      <div className="lg:col-span-3 space-y-6">
        <Card title="Step 4: Select Criteria & View Results" subtitle="Click a result row to see details.">
          <Input
              placeholder="Filter criteria by keyword…"
              value={filterQuery}
              onChange={e => setFilterQuery(e.target.value)}
              disabled={!selectedLawId || loadingCriteria}
          />
          <div className="max-h-[40rem] overflow-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-slate-100/60 text-xs text-slate-600 backdrop-blur-sm">
                  <tr>
                    <th className="w-12 p-3">
                      <input 
                        type="checkbox"
                        checked={filteredCriteria.length > 0 && selectedCriterionIds.length === filteredCriteria.length}
                        onChange={handleSelectAll}
                        disabled={filteredCriteria.length === 0}
                      />
                    </th>
                    <th className="p-3">Requirement Summary</th>
                    <th className="p-3 w-40">Status</th>
                    <th className="p-3 w-28">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingCriteria && <tr><td colSpan={4} className="p-3 text-center text-slate-500">Loading criteria...</td></tr>}
                  {!loadingCriteria && filteredCriteria.length === 0 && <tr><td colSpan={4} className="p-3 text-center text-slate-500">No criteria found.</td></tr>}
                  {filteredCriteria.map(c => {
                      const result = verificationResults[c.criterion_id];
                      const isExpanded = expandedCriterionId === c.criterion_id;
                      const hasResult = result && !result.loading;
                      
                      return (
                        <React.Fragment key={c.criterion_id}>
                          <tr 
                            className={classNames(
                                "border-t border-slate-200",
                                hasResult && "cursor-pointer hover:bg-slate-50",
                                isExpanded && "bg-indigo-50"
                            )}
                            onClick={() => handleRowClick(c.criterion_id)}
                          >
                            <td className="p-3 text-center" onClick={e => e.stopPropagation()}>
                              <input type="checkbox" name="criterion" checked={selectedCriterionIds.includes(c.criterion_id)} onChange={() => handleCriterionToggle(c.criterion_id)} />
                            </td>
                            <td className="p-3 max-w-md">
                              <p className="font-medium text-slate-800" title={c.requirement_summary}>{c.requirement_summary}</p>
                              <Pill>{c.actionable_verb}</Pill>
                            </td>
                            <td className="p-3">
                              {result?.loading && <span className="text-slate-400">Verifying...</span>}
                              {hasResult && result?.compliance_status && (
                                <Pill tone={getComplianceTone(result.compliance_status)}>
                                  <span className="font-bold">{result.compliance_status}</span>
                                </Pill>
                              )}
                            </td>
                            <td className="p-3">
                               {hasResult && typeof result?.confidence_score === 'number' && (
                                  <p className="font-semibold text-slate-700">{(result.confidence_score * 100).toFixed(1)}%</p>
                               )}
                            </td>
                          </tr>
                          {isExpanded && hasResult && (
                              <tr className="border-t border-indigo-200 bg-white">
                                  <td colSpan={4} className="p-4 space-y-4">
                                      <div>
                                          <h4 className="text-xs font-semibold text-slate-500">REASONING</h4>
                                          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700 bg-slate-50 rounded-lg p-3">{result.reasoning}</p>
                                      </div>
                                      <div>
                                          <h4 className="text-xs font-semibold text-slate-500">SUPPORTING EVIDENCE</h4>
                                          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700 bg-slate-50 rounded-lg p-3">{result.supporting_evidence_from_document || "No direct evidence found."}</p>
                                      </div>
                                  </td>
                              </tr>
                          )}
                        </React.Fragment>
                      )
                  })}
                </tbody>
            </table>
          </div>
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