// import { useState } from 'react';
// import { useNavigate } from 'react-router-dom';
// import { adminAPI } from '../services/api';
// import { Button } from '../components/ui/Button';
// import { Input } from '../components/ui/Input';
// import { Car, ShieldCheck } from 'lucide-react';

// function Login({ onLogin }) {
//   const [token, setToken] = useState('');
//   const [error, setError] = useState('');
//   const [loading, setLoading] = useState(false);
//   const navigate = useNavigate();

//   const handleSubmit = async (e) => {
//     e.preventDefault();
//     if (!token.trim()) {
//       setError('Please enter a valid token');
//       return;
//     }

//     setLoading(true);
//     setError('');

//     // localStorage.setItem('adminToken', token);
//     await adminAPI.login({ token });
//     onLogin();
//     navigate('/dashboard');


//     try {
//       await adminAPI.getConfig();
//       onLogin();
//       navigate('/dashboard');
//     } catch (err) {
//       localStorage.removeItem('adminToken');
//       if (err.response?.status === 401 || err.response?.status === 403) {
//         setError('Invalid admin token. Please check and try again.');
//       } else {
//         setError('Failed to connect to server. Make sure the backend is running.');
//       }
//     } finally {
//       setLoading(false);
//     }
//   };

//   return (
//     <div className="min-h-screen flex bg-gray-50">
//       {/* Left Side - Form */}
//       <div className="flex-1 flex flex-col justify-center py-12 px-4 sm:px-6 lg:flex-none lg:px-20 xl:px-24 bg-white border-r border-gray-200 w-full lg:w-[480px]">
//         <div className="mx-auto w-full max-w-sm lg:w-96">
//           <div className="flex items-center gap-2 mb-10">
//             <div className="w-10 h-10 bg-primary-600 rounded-xl flex items-center justify-center shadow-lg shadow-primary-200">
//               <Car className="w-6 h-6 text-white" />
//             </div>
//             <span className="text-2xl font-bold text-gray-900">CarBot Admin</span>
//           </div>

//           <div>
//             <h2 className="text-3xl font-bold tracking-tight text-gray-900">Welcome back</h2>
//             <p className="mt-2 text-sm text-gray-600">
//               Please enter your admin token to access the dashboard.
//             </p>
//           </div>

//           <div className="mt-8">
//             <form onSubmit={handleSubmit} className="space-y-6">
//               <Input
//                 id="token"
//                 label="Admin Token"
//                 type="password"
//                 value={token}
//                 onChange={(e) => setToken(e.target.value)}
//                 placeholder="Enter your admin token"
//                 error={error}
//                 autoFocus
//               />

//               <Button
//                 type="submit"
//                 className="w-full"
//                 isLoading={loading}
//                 size="lg"
//               >
//                 Sign in to Dashboard
//               </Button>
//             </form>

//             <div className="mt-6">
//               <div className="relative">
//                 <div className="absolute inset-0 flex items-center">
//                   <div className="w-full border-t border-gray-300" />
//                 </div>
//                 <div className="relative flex justify-center text-sm">
//                   <span className="bg-white px-2 text-gray-500">Developer Info</span>
//                 </div>
//               </div>

//               <div className="mt-6 grid grid-cols-1 gap-3">
//                 <div className="flex items-center justify-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs text-gray-600">
//                   <ShieldCheck className="w-4 h-4 text-gray-400" />
//                   <span>Default token: <code className="font-mono bg-gray-200 px-1 py-0.5 rounded text-gray-800">admin-token</code></span>
//                 </div>
//               </div>
//             </div>
//           </div>
//         </div>
//       </div>

//       {/* Right Side - Decoration */}
//       <div className="hidden lg:block relative w-0 flex-1 bg-primary-900">
//         <div className="absolute inset-0 h-full w-full object-cover bg-gradient-to-br from-primary-800 to-primary-950 flex items-center justify-center overflow-hidden">
//           <div className="absolute top-0 left-0 w-full h-full opacity-10">
//             <svg className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
//               <path d="M0 100 C 20 0 50 0 100 100 Z" fill="white" />
//             </svg>
//           </div>
//           <div className="relative z-10 text-center px-12">
//             <h2 className="text-4xl font-bold text-white mb-6">Manage your Car Parts Bot</h2>
//             <p className="text-primary-200 text-lg max-w-md mx-auto">
//               Monitor leads, track search statistics, and configure your AI assistant from one central hub.
//             </p>
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// }

// export default Login;
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../services/api';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Car, ShieldCheck } from 'lucide-react';

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
    <div className="min-h-screen flex bg-gray-50">
      {/* Left Side - Form */}
      <div className="flex-1 flex flex-col justify-center py-12 px-4 sm:px-6 lg:flex-none lg:px-20 xl:px-24 bg-white border-r border-gray-200 w-full lg:w-[480px]">
        <div className="mx-auto w-full max-w-sm lg:w-96">

          <div className="flex items-center gap-2 mb-10">
            <div className="w-10 h-10 bg-primary-600 rounded-xl flex items-center justify-center shadow-lg shadow-primary-200">
              <Car className="w-6 h-6 text-white" />
            </div>
            <span className="text-2xl font-bold text-gray-900">
              CarBot Admin
            </span>
          </div>

          <div>
            <h2 className="text-3xl font-bold tracking-tight text-gray-900">
              Welcome back
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              Please enter your admin password to access the dashboard.
            </p>
          </div>

          <div className="mt-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              <Input
                id="token"
                label="Admin Password"
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Enter your admin password"
                error={error}
                autoFocus
              />

              <Button
                type="submit"
                className="w-full"
                isLoading={loading}
                size="lg"
              >
                Sign in to Dashboard
              </Button>
            </form>

            {/* Developer info */}
            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-300" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="bg-white px-2 text-gray-500">
                    Developer Info
                  </span>
                </div>
              </div>

              <div className="mt-6">
                <div className="flex items-center justify-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs text-gray-600">
                  <ShieldCheck className="w-4 h-4 text-gray-400" />
                  <span>
                    Password:{' '}
                    <code className="font-mono bg-gray-200 px-1 py-0.5 rounded text-gray-800">
                      CarBot@Admin2025
                    </code>
                  </span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>

      {/* Right Side - Decoration */}
      <div className="hidden lg:block relative w-0 flex-1 bg-primary-900">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-800 to-primary-950 flex items-center justify-center">
          <div className="relative z-10 text-center px-12">
            <h2 className="text-4xl font-bold text-white mb-6">
              Manage your Car Parts Bot
            </h2>
            <p className="text-primary-200 text-lg max-w-md mx-auto">
              Monitor leads, track search statistics, and configure your AI assistant from one central hub.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;
