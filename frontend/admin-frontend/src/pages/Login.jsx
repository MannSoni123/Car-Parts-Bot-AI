import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../services/api';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Car, ShieldCheck } from 'lucide-react';
import './Login.css'; // Import the new CSS
import car1 from '../assets/cartoon-car-1.png';
import car2 from '../assets/cartoon-car-2.png';

function Login({ onLogin }) {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!token.trim()) {
      setError('Please enter a valid token');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // 🔐 Real authentication (cookie-based)
      await adminAPI.login({ token });

      onLogin();
      navigate('/dashboard', { replace: true });
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        setError('Invalid admin token. Please check and try again.');
      } else {
        setError('Failed to connect to server. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      {/* Animated Cars */}
      <img src={car1} alt="Car 1" className="car-animation car-1" />
      <img src={car2} alt="Car 2" className="car-animation car-2" />

      {/* Centered Glassmorphism Card */}
      <div className="glass-card">
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center shadow-lg mb-4 transform -rotate-6">
            <Car className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">CarBot Admin</h1>
          <p className="text-gray-500 mt-2 text-center">Enter your credentials to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <Input
            id="token"
            label="Admin Password"
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Enter password..."
            error={error}
            autoFocus
            className="bg-white/50 border-gray-300 focus:bg-white transition-all duration-200"
          />

          <Button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl shadow-md transform transition hover:-translate-y-0.5"
            isLoading={loading}
            size="lg"
          >
            Start Engine
          </Button>
        </form>

        <div className="mt-8 pt-6 border-t border-gray-400/20">
          <div className="flex items-center justify-center gap-2 p-2 bg-white/40 rounded-lg text-xs text-gray-600">
            <ShieldCheck className="w-4 h-4 text-gray-500" />
            <span>
              Default: <code className="font-mono font-bold">CarBot@Admin2025</code>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;
