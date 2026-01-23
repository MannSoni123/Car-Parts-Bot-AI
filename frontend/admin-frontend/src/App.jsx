import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

import { adminAPI } from './services/api';

import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import PromptManager from './pages/PromptManager';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);

  // 🔐 Check session on app load
  useEffect(() => {
    const checkAuth = async () => {
      try {
        await adminAPI.me(); // GET /api/admin/me
        setIsAuthenticated(true);
      } catch {
        setIsAuthenticated(false);
      } finally {
        setCheckingAuth(false);
      }
    };

    checkAuth();
  }, []);

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = async () => {
    try {
      await adminAPI.logout(); // optional but recommended
    } catch {
      // ignore
    } finally {
      setIsAuthenticated(false);
    }
  };

  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-xl text-gray-600">Checking session…</div>
      </div>
    );
  }

  return (
    <Router>
      <Routes>

        {/* Login */}
        <Route
          path="/"
          element={
            isAuthenticated ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <Login onLogin={handleLogin} />
            )
          }
        />

        {/* Dashboard */}
        <Route
          path="/dashboard"
          element={
            isAuthenticated ? (
              <Dashboard onLogout={handleLogout} />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />

        {/* Prompt Manager */}
        <Route
          path="/prompts"
          element={
            isAuthenticated ? (
              <PromptManager onLogout={handleLogout} />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />

      </Routes>
    </Router>
  );
}

export default App;
