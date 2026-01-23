
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../services/api';
import { useEffect } from "react";
export default function PromptModal({ data, onClose, onSaved, onLogout }) {
  const [intentKey, setIntentKey] = useState(data?.intent_key || '');
  const [displayName, setDisplayName] = useState(data?.display_name || '');
  const [intentType, setIntentType] = useState(data?.intent_type || 'text');
  const [promptText, setPromptText] = useState(data?.prompt_text || '');
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
      setExistingFile(data.reference_file || null);
      setReferenceFile(null); // never auto-reselect file
    } else {
      // CREATE MODE RESET
      setIntentKey("");
      setDisplayName("");
      setIntentType("text");
      setPromptText("");
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
    <div className="fixed inset-0 flex justify-center items-center bg-black/50 z-50">
      <div className="bg-white p-6 rounded-xl w-[800px] space-y-4">

        <h2 className="text-xl font-semibold">
          {data ? 'Edit Prompt' : 'Create Prompt'}
        </h2>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
            {error}
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

        {/* Intent Type REMOVED - Unified Flow */}

        {/* Prompt Text */}
        <textarea
          className="w-full p-2 border rounded h-96"
          placeholder="Prompt text"
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          disabled={loading}
        />

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
