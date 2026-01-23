// import { useState, useEffect } from 'react';
// import { useNavigate } from 'react-router-dom';
// import { adminAPI } from '../services/api';
// import { ResponsiveContainer, LineChart, Line, Tooltip } from 'recharts';
// import { Layout } from '../components/Layout';
// import { Card } from '../components/ui/Card';
// import { Users, UserPlus, AlertCircle, Brain } from 'lucide-react';
// import { clsx } from 'clsx';
// import { useSSE } from '../hooks/useSSE';
// import { SSE_URL } from '../config/api';
// import { useState, useEffect, useCallback } from 'react';
// import { useCallback } from 'react';


// function Dashboard({ onLogout }) {
//   const [stats, setStats] = useState(null);
//   const [metrics, setMetrics] = useState(null);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState('');
//   const navigate = useNavigate();
//   const [isLoggingOut, setIsLoggingOut] = useState(false);

//   useEffect(() => {
//     if (!localStorage.getItem('adminToken')) {
//       onLogout();
//       navigate('/', { replace: true });
//       return;
//     }
//     fetchData();
//   }, []);

//   // const fetchData = async () => {
//   //   if (isLoggingOut) return;
//   //   try {
//   //     setLoading(true);
//   //     const [statsRes, metricsRes] = await Promise.all([
//   //       adminAPI.getStats(),
//   //       adminAPI.getMetrics(),
//   //     ]);
//   //     setStats(statsRes.data);
//   //     setMetrics(metricsRes.data);
//   //     setError('');
//   //   } catch (err) {
//   //     if (!isLoggingOut && (err.response?.status === 401 || err.response?.status === 403)) {
//   //       onLogout();
//   //       navigate('/', { replace: true });
//   //     } else {
//   //       setError('Failed to fetch data. Check if backend is running.');
//   //     }
//   //   } finally {
//   //     !isLoggingOut && setLoading(false);
//   //   }
//   // };


//   const fetchData = useCallback(async () => {
//     if (isLoggingOut) return;
//     try {
//       setLoading(true);
//       const [statsRes, metricsRes] = await Promise.all([
//         adminAPI.getStats(),
//         adminAPI.getMetrics(),
//       ]);
//       setStats(statsRes.data);
//       setMetrics(metricsRes.data);
//       setError('');
//     } catch (err) {
//       if (
//         !isLoggingOut &&
//         (err.response?.status === 401 || err.response?.status === 403)
//       ) {
//         onLogout();
//         navigate('/', { replace: true });
//       } else {
//         setError('Failed to fetch data. Check if backend is running.');
//       }
//     } finally {
//       !isLoggingOut && setLoading(false);
//     }
//   }, [isLoggingOut, navigate, onLogout]);

//   // Live updates
//   // useSSE('http://localhost:5000/events', () => {
//   //   fetchData();
//   // });
//   useSSE(SSE_URL, fetchData);

//   if (loading) {
//     return (
//       <div className="min-h-screen flex items-center justify-center bg-gray-50">
//         <p className="text-gray-500 font-medium">Loading dashboard...</p>
//       </div>
//     );
//   }

//   return (
//     <Layout onLogout={onLogout}>
//       <div className="space-y-6">

//         {/* Header */}
//         <div>
//           <h1 className="text-2xl font-bold text-gray-900">Dashboard Overview</h1>
//           <p className="text-gray-500 mt-1">Lead activity and AI response performance</p>
//         </div>

//         {error && (
//           <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
//             <AlertCircle className="w-5 h-5" />
//             {error}
//           </div>
//         )}

//         {/* Stats Cards */}
//         <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
//           <StatCard
//             title="Total Leads"
//             value={stats?.total_leads || 0}
//             icon={Users}
//             trend="Counting leads"
//             trendUp={true}
//             color="purple"
//           />
//           <StatCard
//             title="New Leads"
//             value={stats?.new_leads || 0}
//             icon={UserPlus}
//             trend="New incoming"
//             trendUp={false}
//             color="yellow"
//           />
//         </div>

//         {/* AI Performance */}
//         <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
//           <Card className="p-6">
//             <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
//               <Brain className="w-5 h-5 text-primary-500" />
//               AI Performance
//             </h2>
//             <div className="space-y-4">
//               <MetricRow
//                 label="Intent Accuracy"
//                 value={`${metrics?.intent_accuracy_percent?.toFixed(1) || 0}%`}
//                 subtext="Recognizing user requests"
//               />
//               <MetricRow
//                 label="Avg Response Time"
//                 value={`${metrics?.avg_latency?.toFixed(3) || 0}s`}
//                 subtext="Model processing time"
//               />
//               <MetricRow
//                 label="Total Interactions"
//                 value={metrics?.total_intent_checks || 0}
//                 subtext="Since launch"
//               />
//             </div>
//           </Card>

//           <Card className="p-6 lg:col-span-2">
//             <h2 className="text-lg font-semibold text-gray-900 mb-4">Latency Trend</h2>
//             <div className="h-48">
//               <ResponsiveContainer width="100%" height="100%">
//                 <LineChart data={(metrics?.last_100_latencies || []).map((lat, i) => ({ i, lat }))}>
//                   <Line type="monotone" dataKey="lat" strokeWidth={2} dot={false} />
//                   <Tooltip />
//                 </LineChart>
//               </ResponsiveContainer>
//             </div>
//           </Card>
//         </div>

//       </div>
//     </Layout>
//   );
// }

// function StatCard({ title, value, icon: Icon, trend, trendUp, color }) {
//   const colors = {
//     purple: 'bg-purple-50 text-purple-600',
//     yellow: 'bg-yellow-50 text-yellow-600',
//   };

//   return (
//     <Card className="p-6 hover:shadow-md transition-shadow">
//       <div className="flex items-start justify-between">
//         <div>
//           <p className="text-sm text-gray-500">{title}</p>
//           <p className="text-2xl font-bold mt-2">{value}</p>
//         </div>
//         <div className={clsx('p-3 rounded-lg', colors[color])}>
//           <Icon className="w-6 h-6" />
//         </div>
//       </div>
//       <p className={clsx('mt-4 text-sm', trendUp ? 'text-green-600' : 'text-gray-500')}>
//         {trend}
//       </p>
//     </Card>
//   );
// }

// function MetricRow({ label, value, subtext }) {
//   return (
//     <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
//       <div>
//         <p className="font-medium text-gray-900">{label}</p>
//         <p className="text-xs text-gray-500">{subtext}</p>
//       </div>
//       <p className="text-lg font-bold text-gray-900">{value}</p>
//     </div>
//   );
// }

// export default Dashboard;
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../services/api';
import { SSE_URL } from '../config/api';
import { useSSE } from '../hooks/useSSE';

import { ResponsiveContainer, LineChart, Line, Tooltip } from 'recharts';
import { Layout } from '../components/Layout';
import { Card } from '../components/ui/Card';
import { Users, UserPlus, AlertCircle, Brain } from 'lucide-react';
import { clsx } from 'clsx';

function Dashboard({ onLogout }) {
  const [stats, setStats] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const navigate = useNavigate();

  // 🔹 Fetch dashboard data
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);

      const [statsRes, metricsRes] = await Promise.all([
        adminAPI.getStats(),
        adminAPI.getMetrics(),
      ]);

      setStats(statsRes.data);
      setMetrics(metricsRes.data);
      setError('');
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        // Backend decides auth validity
        onLogout();
        navigate('/', { replace: true });
      } else {
        setError('Failed to fetch data. Backend may be unreachable.');
      }
    } finally {
      setLoading(false);
    }
  }, [navigate, onLogout]);

  // 🔹 Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 🔹 Live updates via SSE (signal only)
  useSSE(SSE_URL, fetchData);

  // 🔹 Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500 font-medium">Loading dashboard...</p>
      </div>
    );
  }

  return (
    <Layout onLogout={onLogout}>
      <div className="space-y-6">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard Overview</h1>
          <p className="text-gray-500 mt-1">
            Lead activity and AI response performance
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <StatCard
            title="Total Leads"
            value={stats?.total_leads || 0}
            icon={Users}
            trend="Counting leads"
            trendUp
            color="purple"
          />
          <StatCard
            title="New Leads"
            value={stats?.new_leads || 0}
            icon={UserPlus}
            trend="New incoming"
            trendUp={false}
            color="yellow"
          />
        </div>

        {/* AI Performance */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Brain className="w-5 h-5 text-primary-500" />
              AI Performance
            </h2>

            <div className="space-y-4">
              <MetricRow
                label="Intent Accuracy"
                value={`${metrics?.intent_accuracy_percent?.toFixed(1) || 0}%`}
                subtext="Recognizing user requests"
              />
              <MetricRow
                label="Avg Response Time"
                value={`${metrics?.avg_latency?.toFixed(3) || 0}s`}
                subtext="Model processing time"
              />
              <MetricRow
                label="Total Interactions"
                value={metrics?.total_intent_checks || 0}
                subtext="Since launch"
              />
            </div>
          </Card>

          <Card className="p-6 lg:col-span-2">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Latency Trend
            </h2>

            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={(metrics?.last_100_latencies || []).map((lat, i) => ({
                    i,
                    lat,
                  }))}
                >
                  <Line type="monotone" dataKey="lat" strokeWidth={2} dot={false} />
                  <Tooltip />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

      </div>
    </Layout>
  );
}

function StatCard({ title, value, icon: Icon, trend, trendUp, color }) {
  const colors = {
    purple: 'bg-purple-50 text-purple-600',
    yellow: 'bg-yellow-50 text-yellow-600',
  };

  return (
    <Card className="p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold mt-2">{value}</p>
        </div>
        <div className={clsx('p-3 rounded-lg', colors[color])}>
          <Icon className="w-6 h-6" />
        </div>
      </div>

      <p className={clsx('mt-4 text-sm', trendUp ? 'text-green-600' : 'text-gray-500')}>
        {trend}
      </p>
    </Card>
  );
}

function MetricRow({ label, value, subtext }) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
      <div>
        <p className="font-medium text-gray-900">{label}</p>
        <p className="text-xs text-gray-500">{subtext}</p>
      </div>
      <p className="text-lg font-bold text-gray-900">{value}</p>
    </div>
  );
}

export default Dashboard;
