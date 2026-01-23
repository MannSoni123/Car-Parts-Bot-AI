
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
            className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-5 py-2.5 rounded-xl hover:shadow-lg hover:from-blue-700 hover:to-indigo-700 transition-all duration-300 font-medium shadow-md flex items-center gap-2 transform hover:-translate-y-0.5"
          >
            + New Prompt
          </button>
        </div>

        {/* Error */}
        {error && <p className="text-red-600">{error}</p>}

        {/* Table */}
        <Card className="p-6 shadow-xl border border-gray-100 rounded-xl overflow-hidden animate-in fade-in duration-700">
          {loading ? (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
          ) : (
            <table className="min-w-full">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  <th className="p-4 text-left font-semibold text-gray-600 uppercase text-xs tracking-wider">Prompt Name</th>
                  <th className="p-4 text-left font-semibold text-gray-600 uppercase text-xs tracking-wider">Status</th>
                  <th className="p-4 text-left font-semibold text-gray-600 uppercase text-xs tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {prompts.map((p) => (
                  <tr key={p.id} className="hover:bg-blue-50/50 transition-all duration-300 group">
                    <td className="p-4">
                      <div className="font-semibold text-gray-800">{p.display_name}</div>
                      <div className="text-xs text-gray-400 font-mono mt-1">{p.intent_key}</div>
                    </td>

                    {/* Status */}
                    <td className="p-4">
                      <button
                        onClick={() => {
                          const action = p.is_active ? 'deactivate' : 'activate';
                          if (window.confirm(`Are you sure you want to ${action} this prompt?`)) {
                            handleToggle(p.id);
                          }
                        }}
                        className={`px-3 py-1 rounded-full text-xs font-medium transition-all duration-300 ${p.is_active
                          ? 'bg-gradient-to-r from-emerald-400/10 to-emerald-500/10 text-emerald-700 border border-emerald-200 hover:border-emerald-300'
                          : 'bg-gray-100 text-gray-500 border border-gray-200 hover:border-gray-300'
                          }`}
                      >
                        <span className={`inline-block w-2 h-2 rounded-full mr-2 ${p.is_active ? 'bg-emerald-500' : 'bg-gray-400'}`}></span>
                        {p.is_active ? 'Active' : 'Inactive'}
                      </button>
                    </td>

                    {/* Actions */}
                    <td className="p-4 flex gap-4 opacity-70 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => {
                          setSelected(p);
                          setModalOpen(true);
                        }}
                        className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                        title="Edit"
                      >
                        <Edit size={18} />
                      </button>

                      <button
                        onClick={() => handleDelete(p.id)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
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
