import { useState } from "react";
import { ingestLawDocument } from "../lib/api";
import { IngestLawPayload } from "../lib/types";
import { Button, Card, Input, Pill, TextArea } from "./ui";

export function AdminView() {
  const [formData, setFormData] = useState<Omit<IngestLawPayload, 'law_full_text'>>({
    law_name: "",
    law_citation: "",
    law_acronym: "",
    region: "",
  });
  const [lawText, setLawText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleIngest = async () => {
    if (!lawText.trim()) {
      setMessage({ text: "Please paste the legal text to ingest.", type: "error" });
      return;
    }
    setIsLoading(true);
    setMessage(null);
    try {
      const payload: IngestLawPayload = {
        law_full_text: lawText,
        law_name: formData.law_name || null,
        law_citation: formData.law_citation || null,
        law_acronym: formData.law_acronym || null,
        region: formData.region || null,
      };
      await ingestLawDocument(payload);
      setMessage({ text: "Ingestion successful! The document will be available for compliance checks shortly.", type: "success" });
      // Reset form
      setLawText("");
      setFormData({ law_name: "", law_citation: "", law_acronym: "", region: "" });
    } catch (e: any) {
      setMessage({ text: `Ingestion failed: ${e.message}`, type: "error" });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
       <div className="text-center">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">Stage 1: Ingest Legal Document</h2>
            <p className="mt-2 text-sm text-slate-600">
                As an administrator, you can add new legal texts to the system. The API will extract compliance criteria automatically.
            </p>
        </div>
      <Card title="New Legal Document" subtitle="Paste the full text of the law and add optional metadata.">
        <TextArea
          rows={12}
          placeholder="Paste the entire legal text here…"
          value={lawText}
          onChange={(e) => setLawText(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-4">
          <Input placeholder="Law name (e.g., General Data Protection Regulation)" name="law_name" value={formData.law_name || ''} onChange={handleInputChange} />
          <Input placeholder="Citation (e.g., Regulation (EU) 2016/679)" name="law_citation" value={formData.law_citation || ''} onChange={handleInputChange} />
          <Input placeholder="Acronym (e.g., GDPR)" name="law_acronym" value={formData.law_acronym || ''} onChange={handleInputChange} />
          <Input placeholder="Region (e.g., European Union)" name="region" value={formData.region || ''} onChange={handleInputChange} />
        </div>
        <div className="flex items-center justify-between pt-2">
          <Button onClick={handleIngest} loading={isLoading}>
            Ingest & Extract Criteria
          </Button>
          <Pill>Criteria stored in database</Pill>
        </div>
        {message && (
          <div className={`mt-4 rounded-lg p-3 text-sm ${message.type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {message.text}
          </div>
        )}
      </Card>
    </div>
  );
}