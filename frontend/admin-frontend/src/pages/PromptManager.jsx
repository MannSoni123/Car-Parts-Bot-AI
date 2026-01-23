// import { useEffect, useState } from "react";
// import { adminAPI } from "../services/api";
// import { Layout } from "../components/Layout";
// import { Card } from "../components/ui/Card";
// import PromptModal from "./PromptModal";
// import { Trash2, Edit } from "lucide-react";

// function PromptManager({ onLogout }) {
//   const [prompts, setPrompts] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState("");
//   const [selected, setSelected] = useState(null);
//   const [modalOpen, setModalOpen] = useState(false);

//   const fetchPrompts = async () => {
//     try {
//       setLoading(true);
//       const res = await adminAPI.getPrompts();
//       setPrompts(res.data || []);
//     } catch (err) {
//       console.error(err);
//       setError("Failed to load prompts.");
//     } finally {
//       setLoading(false);
//     }
//   };

//   useEffect(() => {
//     fetchPrompts();
//   }, []);

//   const handleDelete = async (id) => {
//     if (!window.confirm("Are you sure?")) return;
//     await adminAPI.deletePrompt(id);
//     fetchPrompts();
//   };

//   const handleToggle = async (id) => {
//     await adminAPI.togglePrompt(id);
//     fetchPrompts();
//   };

//   return (
//     <Layout onLogout={onLogout}>
//       <div className="space-y-6">
//         <div className="flex items-center justify-between">
//           <h1 className="text-2xl font-bold">Handle Prompts</h1>
//           <button
//             onClick={() => {
//               setSelected(null);
//               setModalOpen(true);
//             }}
//             className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition"
//           >
//             + Add Prompt
//           </button>
//         </div>

//         {error && <p className="text-red-600">{error}</p>}

//         <Card className="p-6">
//           {loading ? (
//             <p className="text-gray-500">Loading prompts...</p>
//           ) : (
//             <table className="min-w-full border">
//               <thead className="bg-gray-100">
//                 <tr>
//                   <th className="p-3 text-left">Intent Key</th>
//                   <th className="p-3 text-left">Status</th>
//                   <th className="p-3 text-left">Actions</th>
//                 </tr>
//               </thead>
//               <tbody>
//                 {prompts.map((p) => (
//                   <tr key={p.id} className="border-t">
//                     <td className="p-3 font-medium">{p.intent_key}</td>
//                     <td className="p-3">
//                       <button
//                         onClick={() => handleToggle(p.id)}
//                         className={`px-3 py-1 rounded text-sm ${
//                           p.is_active
//                             ? "bg-green-100 text-green-700"
//                             : "bg-gray-200 text-gray-600"
//                         }`}
//                       >
//                         {p.is_active ? "Active" : "Inactive"}
//                       </button>
//                     </td>
//                     <td className="p-3 flex gap-3">
//                       <button
//                         onClick={() => {
//                           setSelected(p);
//                           setModalOpen(true);
//                         }}
//                         className="text-blue-600 hover:text-blue-800"
//                       >
//                         <Edit size={18} />
//                       </button>
//                       <button
//                         onClick={() => handleDelete(p.id)}
//                         className="text-red-600 hover:text-red-800"
//                       >
//                         <Trash2 size={18} />
//                       </button>
//                     </td>
//                   </tr>
//                 ))}
//               </tbody>
//             </table>
//           )}
//         </Card>
//       </div>

//       {modalOpen && (
//         <PromptModal
//           data={selected}
//           onClose={() => setModalOpen(false)}
//           onSaved={fetchPrompts}
//         />
//       )}
//     </Layout>
//   );
// }

// export default PromptManager;
import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../services/api';
import { Layout } from '../components/Layout';
import { Card } from '../components/ui/Card';
import PromptModal from './PromptModal';
import { Trash2, Edit } from 'lucide-react';

function PromptManager({ onLogout }) {
  const [prompts, setPrompts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);

  const navigate = useNavigate();

  // 🔹 Fetch prompts
  const fetchPrompts = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const res = await adminAPI.getPrompts();
      setPrompts(res.data || []);
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        onLogout();
        navigate('/', { replace: true });
      } else {
        setError('Failed to load prompts.');
      }
    } finally {
      setLoading(false);
    }
  }, [navigate, onLogout]);

  useEffect(() => {
    fetchPrompts();
  }, [fetchPrompts]);

  // 🔹 Delete prompt
  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this prompt?')) return;

    try {
      await adminAPI.deletePrompt(id);
      fetchPrompts();
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        onLogout();
        navigate('/', { replace: true });
      } else {
        alert('Failed to delete prompt.');
      }
    }
  };

  // 🔹 Toggle prompt
  const handleToggle = async (id) => {
    try {
      await adminAPI.togglePrompt(id);
      fetchPrompts();
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        onLogout();
        navigate('/', { replace: true });
      } else {
        alert('Failed to update prompt status.');
      }
    }
  };

  return (
    <Layout onLogout={onLogout}>
      <div className="space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Prompt Management</h1>
          <button
            onClick={() => {
              setSelected(null);
              setModalOpen(true);
            }}
            className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition"
          >
            + Add Prompt
          </button>
        </div>

        {/* Error */}
        {error && <p className="text-red-600">{error}</p>}

        {/* Table */}
        <Card className="p-6">
          {loading ? (
            <p className="text-gray-500">Loading prompts...</p>
          ) : (
            <table className="min-w-full border">
              <thead className="bg-gray-100">
                <tr>
                  <th className="p-3 text-left">Prompt Name</th>
                  <th className="p-3 text-left">Type</th>
                  <th className="p-3 text-left">Status</th>
                  <th className="p-3 text-left">Actions</th>
                </tr>
              </thead>
              <tbody>
                {prompts.map((p) => (
                  <tr key={p.id} className="border-t">
                    <td className="p-3">
                      <div className="font-medium">{p.display_name}</div>
                    </td>

                    {/* Intent Type Badge */}
                    <td className="p-3">
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${
                          p.intent_type === 'image'
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-blue-100 text-blue-700'
                        }`}
                      >
                        {p.intent_type === 'image' ? 'Image' : 'Text'}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="p-3">
                      <button
                        onClick={() => {
                          const action = p.is_active ? 'deactivate' : 'activate';
                          if (window.confirm(`Are you sure you want to ${action} this prompt?`)) {
                            handleToggle(p.id);
                          }
                        }}
                        className={`px-3 py-1 rounded text-sm ${
                          p.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-200 text-gray-600'
                        }`}
                      >
                        {p.is_active ? 'Active' : 'Inactive'}
                      </button>
                    </td>

                    {/* Actions */}
                    <td className="p-3 flex gap-3">
                      <button
                        onClick={() => {
                          setSelected(p);
                          setModalOpen(true);
                        }}
                        className="text-blue-600 hover:text-blue-800"
                        title="Edit"
                      >
                        <Edit size={18} />
                      </button>

                      <button
                        onClick={() => handleDelete(p.id)}
                        className="text-red-600 hover:text-red-800"
                        title="Delete"
                      >
                        <Trash2 size={18} />
                      </button>
                    </td>
                  </tr>

                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      {/* Modal */}
      {modalOpen && (
        <PromptModal
          data={selected}
          onClose={() => setModalOpen(false)}
          onSaved={fetchPrompts}
        />
      )}
    </Layout>
  );
}

export default PromptManager;
