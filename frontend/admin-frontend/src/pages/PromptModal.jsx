
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../services/api';
import { useEffect } from "react";
export default function PromptModal({ data, onClose, onSaved, onLogout }) {
  const [intentKey, setIntentKey] = useState(data?.intent_key || '');
  const [displayName, setDisplayName] = useState(data?.display_name || '');
  const [intentType, setIntentType] = useState(data?.intent_type || 'text');
  const [promptText, setPromptText] = useState(data?.prompt_text || '');
  const [partsAliasText, setPartsAliasText] = useState(data?.parts_alias_text || '');
  const [clarificationRules, setClarificationRules] = useState(data?.clarification_rules || '');
  const [vipNumbers, setVipNumbers] = useState(data?.vip_numbers || '');
  const [showVip, setShowVip] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [referenceFile, setReferenceFile] = useState(null);
  const [existingFile, setExistingFile] = useState(
    data?.reference_file || null
  );


  const navigate = useNavigate();
  useEffect(() => {
    if (data) {
      setIntentKey(data.intent_key || "");
      setDisplayName(data.display_name || "");
      setIntentType(data.intent_type || "text");
      setPromptText(data.prompt_text || "");
      setPartsAliasText(data.parts_alias_text || "");
      setClarificationRules(data.clarification_rules || "");
      setVipNumbers(data.vip_numbers || "");
      setExistingFile(data.reference_file || null);
      setReferenceFile(null); // never auto-reselect file
    } else {
      // CREATE MODE RESET
      setIntentKey("");
      setDisplayName("");
      setIntentType("text");
      setPromptText("");
      setPartsAliasText("");
      setClarificationRules("");
      setVipNumbers("");
      setExistingFile(null);
      setReferenceFile(null);
    }
  }, [data]);

  const save = async () => {
    if (!displayName.trim() || !promptText.trim() || !intentType) {
      setError("All fields are required");
      return;
    }

    if (!data && !intentKey.trim()) {
      setError("Intent key is required");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();

      // common fields
      formData.append("display_name", displayName.trim());
      formData.append("prompt_text", promptText.trim());
      formData.append("parts_alias_text", partsAliasText.trim());
      formData.append("clarification_rules", clarificationRules.trim());
      formData.append("vip_numbers", vipNumbers.trim());
      formData.append("intent_type", "super_intent");

      // only on CREATE
      if (!data) {
        formData.append(
          "intent_key",
          intentKey.toLowerCase().replace(/[^a-z0-9_]/g, "_")
        );
      }

      // Attach file if present (Unconditional)
      if (referenceFile) {
        formData.append("reference_file", referenceFile); // ✅ correct key
      }

      // Handle removal
      if (
        data &&
        (!existingFile && !referenceFile) // explicitly removed
      ) {
        formData.append("remove_reference_file", "true");
      }

      // ONE request only
      if (data) {
        await adminAPI.updatePromptMultipart(data.id, formData);
      } else {
        await adminAPI.createPromptMultipart(formData);
      }

      onSaved();
      onClose();

    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        onLogout?.();
        navigate("/", { replace: true });
      } else {
        setError(err.response?.data?.error || "Failed to save prompt");
      }
    } finally {
      setLoading(false);
    }
  };



  return (
    <div className="fixed inset-0 flex justify-center items-center bg-black/50 z-50" onClick={onClose}>
      <div className="bg-white p-6 rounded-xl w-[1300px] space-y-4 max-h-[95vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>

        <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold">
            {data ? 'Edit Prompt' : 'Create Prompt'}
          </h2>
          <button
            type="button"
            className="bg-purple-600 text-white px-3 py-1 rounded text-sm hover:bg-purple-700"
            onClick={() => setShowVip(!showVip)}
          >
            {showVip ? 'Hide VIP Access' : 'VIP Access'}
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
            {error}
          </div>
        )}

        {/* VIP Section (Conditional) */}
        {showVip && (
          <div className="bg-purple-50 p-4 rounded border border-purple-200 space-y-2">
            <label className="text-xs font-semibold uppercase text-purple-700">VIP Numbers (Comma Separated)</label>
            <textarea
              className="w-full p-2 border border-purple-300 rounded h-[100px] font-mono text-sm"
              placeholder="971551517862, 919876543210"
              value={vipNumbers}
              onChange={(e) => setVipNumbers(e.target.value)}
              disabled={loading}
            />
          </div>
        )}

        {/* Intent Key */}
        <input
          className={`w-full p-2 border rounded ${data ? 'bg-gray-100 cursor-not-allowed' : 'bg-white'
            }`}
          placeholder="Intent Key (machine-safe)"
          value={intentKey}
          onChange={(e) => setIntentKey(e.target.value)}
          disabled={!!data}
        />

        {/* Display Name */}
        <input
          className="w-full p-2 border rounded"
          placeholder="Display Name (human-readable)"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          disabled={loading}
        />

        {/* Side-by-Side Area */}
        <div className="flex gap-4">
          {/* Prompt Text (Left) */}
          <div className="flex-1 space-y-2">
            <label className="text-xs font-semibold uppercase text-gray-500">System Prompt</label>
            <textarea
              className="w-full p-2 border rounded h-[400px]"
              placeholder="Prompt text"
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              disabled={loading}
            />
          </div>

          {/* Parts Alias Text (Right) */}
          <div className="flex-1 space-y-2">
            <label className="text-xs font-semibold uppercase text-gray-500">Parts Aliases (Normalization)</label>
            <textarea
              className="w-full p-2 border rounded h-[400px] font-mono text-sm"
              placeholder="bonnet -> hood"
              value={partsAliasText}
              onChange={(e) => setPartsAliasText(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        {/* Clarification Rules (New Section) */}
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase text-gray-500">Clarification Rules</label>
          <textarea
            className="w-full p-2 border rounded h-[200px] font-mono text-sm"
            placeholder={'Oil Seal -> Ask "Engine or Gearbox?"\nVacuum Hose -> Ask "Engine Side or Brake Booster?"'}
            value={clarificationRules}
            onChange={(e) => setClarificationRules(e.target.value)}
            disabled={loading}
          />
        </div>

        {/* Reference File Section (Always Available) */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Reference File (PDF / TXT) - Optional
          </label>

          {existingFile ? (
            <div className="flex items-center gap-3 bg-gray-50 border p-2 rounded">
              <span className="text-sm text-gray-700">
                📄 {existingFile.split("/").pop()}
              </span>

              <button
                type="button"
                onClick={() => setExistingFile(null)}
                className="text-red-600 text-sm hover:underline"
              >
                Remove
              </button>
            </div>
          ) : (
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(e) => setReferenceFile(e.target.files[0])}
              disabled={loading}
              className="w-full border p-2 rounded"
            />
          )}
        </div>

        <div className="flex justify-end gap-2">
          <button onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button
            disabled={loading}
            onClick={save}
            className="bg-primary-600 text-white px-4 py-2 rounded"
          >
            {loading ? 'Saving…' : 'Save'}
          </button>
        </div>

      </div>
    </div>
  );
}
