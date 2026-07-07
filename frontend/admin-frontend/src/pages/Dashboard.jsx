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
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../services/api';
import { SSE_URL } from '../config/api';
import { useSSE } from '../hooks/useSSE';

import { ResponsiveContainer, BarChart, Bar, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { Layout } from '../components/Layout';
import { Card } from '../components/ui/Card';
import { Users, AlertCircle, ChevronDown, ChevronUp, BarChart2, Calendar, Clock, Download } from 'lucide-react';
import { clsx } from 'clsx';

function Dashboard({ onLogout, userRole }) {
  const [activeTab, setActiveTab] = useState('usage'); // 'usage' | 'vin' | 'parts'
  const [stats, setStats] = useState(null);
  const [trends, setTrends] = useState({ daily: [], weekly: [], custom: [] });
  const [trendView, setTrendView] = useState('daily'); // 'daily' | 'weekly' | 'custom'

  // Custom Date Range State (Default: Last 7 Days)
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0]);

  const [users, setUsers] = useState([]);
  const [showUsers, setShowUsers] = useState(false);
  const [loading, setLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(false);
  const [error, setError] = useState('');

  // Peak Usage State
  const [peakUsageData, setPeakUsageData] = useState(null);
  const [peakUsageDate, setPeakUsageDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [showPeakUsageModal, setShowPeakUsageModal] = useState(false);
  const [peakUsageLoading, setPeakUsageLoading] = useState(false);

  // VIN Performance State
  const [vinPerformance, setVinPerformance] = useState(null);
  const [showVinUsersModal, setShowVinUsersModal] = useState(false);

  // Part Demand Intelligence State
  const [topParts, setTopParts] = useState(null);
  const [outOfStockItems, setOutOfStockItems] = useState([]);
  const [oosPage, setOosPage] = useState(1);
  const OOS_ITEMS_PER_PAGE = 5;

  // Export State
  const [isExporting, setIsExporting] = useState(false);

  const navigate = useNavigate();

  // 🔹 Fetch dashboard stats and trends (Using refs or direct state but deliberately preventing auto-fire on date change)
  const fetchDashboardData = useCallback(async (isCustomFetch = false) => {
    try {
      setLoading(true);

      // When the user explicitly clicks Apply, `isCustomFetch` will be true 
      // OR if we are just on the 'daily'/'weekly' tabs, we grab standard data
      const s = (trendView === 'custom' && isCustomFetch) || trendView === 'custom' ? startDate : null;
      const e = (trendView === 'custom' && isCustomFetch) || trendView === 'custom' ? endDate : null;

      const [statsRes, trendsRes, peakRes, vinRes, topPartsRes, oosRes] = await Promise.all([
        adminAPI.getStats(),
        adminAPI.getTrends(s, e),
        adminAPI.getPeakUsage(), // Default load for today's peak hour stat card
        adminAPI.getVinPerformance(),
        adminAPI.getTopParts(),
        adminAPI.getOutOfStock()
      ]);
      setStats(statsRes.data);
      setTrends(trendsRes.data);
      setPeakUsageData(peakRes.data);
      setVinPerformance(vinRes.data);
      setTopParts(topPartsRes.data);
      setOutOfStockItems(oosRes.data.out_of_stock_items || []);
      setError('');
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        onLogout();
        navigate('/', { replace: true });
      } else {
        setError('Failed to fetch dashboard data. Backend may be unreachable.');
      }
    } finally {
      setLoading(false);
    }
  }, [navigate, onLogout, trendView, startDate, endDate]);

  // 🔹 Fetch users list
  const fetchUsers = async () => {
    try {
      setUsersLoading(true);
      const usersRes = await adminAPI.getUsers();
      setUsers(usersRes.data);
    } catch (err) {
      setError('Failed to fetch users list.');
    } finally {
      setUsersLoading(false);
    }
  };

  // 🔹 Handle Export Analytics
  const handleExportAnalytics = async () => {
    try {
      setIsExporting(true);
      const res = await adminAPI.exportAnalytics();

      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'analytics_export.csv');
      document.body.appendChild(link);
      link.click();

      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to export analytics data.');
    } finally {
      setIsExporting(false);
    }
  };

  // 🔹 Fetch Peak Usage
  const fetchPeakUsage = async (dateStr) => {
    try {
      setPeakUsageLoading(true);
      const res = await adminAPI.getPeakUsage(dateStr);
      setPeakUsageData(res.data);
    } catch (err) {
      setError('Failed to fetch peak usage data.');
    } finally {
      setPeakUsageLoading(false);
    }
  };

  // 🔹 Toggle and load users
  const handleToggleUsers = () => {
    if (!showUsers && users.length === 0) {
      fetchUsers();
    }
    setShowUsers(!showUsers);
  };

  // 🔹 Initial load and View Change (but DO NOT auto-fetch if we are just typing in custom dates)
  useEffect(() => {
    // We only auto-fetch when switching tabs to Daily or Weekly.
    // We rely on the "Apply" button to fetch when in Custom mode.
    if (trendView !== 'custom') {
      fetchDashboardData();
    }
  }, [trendView]); // <-- REMOVED fetchDashboardData from deps to stop infinite/unwanted reloads

  // 🔹 Live updates via SSE (signal only)
  useSSE(SSE_URL, () => {
    fetchDashboardData();
    if (showUsers) {
      fetchUsers();
    }
  });

  // 🔹 Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500 font-medium">Loading dashboard...</p>
      </div>
    );
  }

  const chartData = (trendView === 'daily'
    ? trends?.daily
    : trendView === 'weekly'
      ? trends?.weekly
      : trends?.custom) || [];

  // Pagination for OOS items
  const totalOosPages = Math.ceil((outOfStockItems?.length || 0) / OOS_ITEMS_PER_PAGE);
  const paginatedOosItems = (outOfStockItems || []).slice(
    (oosPage - 1) * OOS_ITEMS_PER_PAGE,
    oosPage * OOS_ITEMS_PER_PAGE
  );

  return (
    <Layout onLogout={onLogout} userRole={userRole}>
      <div className="space-y-6">

        {/* Header & Navigation */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-gray-200 pb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard Overview</h1>
            <p className="text-gray-500 mt-1">
              Analytics and customer interactions
            </p>
          </div>

          {/* Top-Right Navigation Tabs */}
          <div className="flex bg-gray-100 p-1 rounded-lg self-start md:self-auto overflow-x-auto custom-scrollbar flex-shrink-0 max-w-full">
            <button
              onClick={() => setActiveTab('usage')}
              className={clsx(
                "px-4 py-2 text-sm font-medium rounded-md transition-colors whitespace-nowrap",
                activeTab === 'usage' ? "bg-white text-indigo-700 shadow-sm" : "text-gray-600 hover:text-gray-900 hover:bg-gray-50/50"
              )}
            >
              Usage & Adoption Insights
            </button>
            <button
              onClick={() => setActiveTab('vin')}
              className={clsx(
                "px-4 py-2 text-sm font-medium rounded-md transition-colors whitespace-nowrap",
                activeTab === 'vin' ? "bg-white text-indigo-700 shadow-sm" : "text-gray-600 hover:text-gray-900 hover:bg-gray-50/50"
              )}
            >
              VIN Search Performance
            </button>
            <button
              onClick={() => setActiveTab('parts')}
              className={clsx(
                "px-4 py-2 text-sm font-medium rounded-md transition-colors whitespace-nowrap",
                activeTab === 'parts' ? "bg-white text-indigo-700 shadow-sm" : "text-gray-600 hover:text-gray-900 hover:bg-gray-50/50"
              )}
            >
              Part Demand Intelligence
            </button>
          </div>
          <button
            onClick={handleExportAnalytics}
            disabled={isExporting}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ml-auto md:ml-0"
          >
            <Download className="w-4 h-4" />
            {isExporting ? 'Exporting...' : 'Export CSV'}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2 mb-6">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}

        {/* --- TAB CONTENT: Usage & Adoption Insights --- */}
        {activeTab === 'usage' && (
          <div className="space-y-6">
            {/* Stats Section */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <button
                onClick={handleToggleUsers}
                className="text-left w-full focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 rounded-xl transition-all h-full"
              >
                <StatCard
                  title="Total Customer Queries via WhatsApp"
                  value={stats?.total_customers || 0}
                  icon={Users}
                  color="purple"
                  trend={showUsers ? "Hide user list" : "Click to view unique users"}
                  trendIcon={showUsers ? ChevronUp : ChevronDown}
                />
              </button>

              <button
                onClick={() => setShowPeakUsageModal(true)}
                className="text-left w-full focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 rounded-xl transition-all h-full"
              >
                <StatCard
                  title="Peak Usage Time (Today)"
                  value={peakUsageData?.peak_hour || "N/A"}
                  icon={Clock}
                  color="yellow"
                  trend="Click to view hourly breakdown"
                  trendIcon={BarChart2}
                />
              </button>
            </div>

            {/* Trends Graph Block (Full Width) */}
            <Card className="p-6 flex flex-col h-full border-gray-100 shadow-sm hover:shadow-lg transition-all relative overflow-hidden">
              <div className="flex flex-col mb-6 z-10 gap-4">

                {/* Top Row: Title & Toggle Buttons */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <div className="flex items-center gap-2">
                    <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
                      <BarChart2 className="w-5 h-5" />
                    </div>
                    <h2 className="text-lg font-semibold text-gray-900 whitespace-nowrap">Query Volume Trends</h2>
                  </div>

                  <div className="bg-gray-100 p-1 rounded-lg flex shrink-0">
                    <button
                      onClick={() => setTrendView('daily')}
                      className={clsx(
                        "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
                        trendView === 'daily' ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-900"
                      )}
                    >
                      30 Days
                    </button>
                    <button
                      onClick={() => setTrendView('weekly')}
                      className={clsx(
                        "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
                        trendView === 'weekly' ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-900"
                      )}
                    >
                      12 Weeks
                    </button>
                    <button
                      onClick={() => setTrendView('custom')}
                      className={clsx(
                        "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
                        trendView === 'custom' ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-900"
                      )}
                    >
                      Custom
                    </button>
                  </div>
                </div>

                {/* Bottom Row: Custom Date Pickers (Only visible when Custom is selected) */}
                {trendView === 'custom' && (
                  <div className="flex flex-wrap items-center justify-start sm:justify-end gap-3 mt-2 animate-in fade-in slide-in-from-top-2">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center bg-white border border-gray-200 rounded-md px-3 py-1.5 shadow-sm transition-colors focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500">
                        <Calendar className="w-4 h-4 text-gray-400 mr-2 shrink-0" />
                        <input
                          type="date"
                          value={startDate}
                          onChange={(e) => setStartDate(e.target.value)}
                          className="text-sm text-gray-700 outline-none bg-transparent w-[120px]"
                        />
                      </div>
                      <span className="text-gray-400 text-sm font-medium">to</span>
                      <div className="flex items-center bg-white border border-gray-200 rounded-md px-3 py-1.5 shadow-sm transition-colors focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500">
                        <Calendar className="w-4 h-4 text-gray-400 mr-2 shrink-0" />
                        <input
                          type="date"
                          value={endDate}
                          onChange={(e) => setEndDate(e.target.value)}
                          className="text-sm text-gray-700 outline-none bg-transparent w-[120px]"
                        />
                      </div>
                    </div>

                    {/* Explicit Fetch Button so the user controls when the screen reloads */}
                    <button
                      onClick={() => fetchDashboardData(true)}
                      className="px-5 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-md shadow-sm hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 shrink-0 w-full sm:w-auto"
                    >
                      Apply
                    </button>
                  </div>
                )}
              </div>

              <div className="w-full h-[320px] z-10 pt-4">
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                      <XAxis
                        dataKey="date"
                        axisLine={false}
                        tickLine={false}
                        tickMargin={10}
                        tick={{ fill: '#6B7280', fontSize: 12 }}
                        minTickGap={20}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#6B7280', fontSize: 12 }}
                        tickMargin={10}
                      />
                      <Tooltip
                        cursor={{ fill: '#F3F4F6' }}
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                        formatter={(value) => [`${value} queries`, 'Volume']}
                      />
                      <Bar
                        dataKey="count"
                        fill="#6366F1"
                        radius={[4, 4, 0, 0]}
                        barSize={trendView === 'weekly' ? 32 : 12}
                        animationDuration={1000}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-sm text-gray-400">
                    {trendView === 'custom' ? 'No query data found for this date range.' : 'No trend data available.'}
                  </div>
                )}
              </div>
              {/* Background decoration */}
              <div className="absolute -bottom-24 -right-24 w-64 h-64 bg-indigo-50 rounded-full blur-3xl opacity-50 pointer-events-none"></div>
            </Card>

            {/* Dynamic Users Modal (Perfect Popup) */}
            {showUsers && createPortal(
              <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
                {/* Dark/Blurred Overlay */}
                <div
                  className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm transition-opacity"
                  onClick={() => setShowUsers(false)}
                ></div>

                {/* Modal Content container - Edge to Edge Design */}
                <div className="relative w-full max-w-3xl max-h-[85vh] flex flex-col bg-white rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 fade-in duration-200 z-10">

                  {/* Header */}
                  <div className="flex justify-between items-center px-6 py-5 border-b border-gray-100 bg-white flex-shrink-0">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-indigo-50 rounded-xl">
                        <Users className="w-5 h-5 text-indigo-600" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-gray-900 leading-tight">Unique Customers</h2>
                        <p className="text-sm text-gray-500">List of users who have interacted with the bot</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      {usersLoading && <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full animate-pulse">Refreshing...</span>}
                      <button
                        onClick={() => setShowUsers(false)}
                        className="text-gray-400 hover:text-gray-600 hover:bg-gray-100 p-2 rounded-full transition-colors flex-shrink-0 focus:outline-none"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                      </button>
                    </div>
                  </div>

                  {/* Scrollable Content Area */}
                  <div className="overflow-y-auto flex-1 bg-gray-50 custom-scrollbar">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-100 sticky top-0 z-10 shadow-sm">
                        <tr>
                          <th className="px-6 py-3.5 text-left text-xs font-bold text-gray-600 uppercase tracking-wider">
                            Customer Number
                          </th>
                          <th className="px-6 py-3.5 text-left text-xs font-bold text-gray-600 uppercase tracking-wider">
                            Total Queries
                          </th>
                          <th className="px-6 py-3.5 text-left text-xs font-bold text-gray-600 uppercase tracking-wider">
                            Last Active (UAE)
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-100">
                        {users.length === 0 && !usersLoading ? (
                          <tr>
                            <td colSpan="3" className="px-6 py-16 text-center text-sm text-gray-500">
                              <div className="flex flex-col items-center gap-3">
                                <div className="p-4 bg-gray-100 rounded-full">
                                  <Users className="w-8 h-8 text-gray-400" />
                                </div>
                                <p className="text-base text-gray-600">No customer queries recorded yet.</p>
                              </div>
                            </td>
                          </tr>
                        ) : (
                          users.map((user, idx) => (
                            <tr key={idx} className="hover:bg-indigo-50/30 transition-colors">
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center">
                                  <div className="h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-sm mr-3">
                                    {idx + 1}
                                  </div>
                                  <span className="text-sm font-medium text-gray-900">
                                    +{user.whatsapp_user_id}
                                  </span>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100 shadow-sm">
                                  {user.total_queries} {user.total_queries === 1 ? 'Query' : 'Queries'}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                <div className="flex items-center text-gray-600">
                                  <Calendar className="w-4 h-4 mr-1.5 text-gray-400" />
                                  {user.last_active
                                    ? new Date(user.last_active).toLocaleString('en-US', {
                                      timeZone: 'Asia/Dubai',
                                      year: 'numeric', month: 'short', day: 'numeric',
                                      hour: '2-digit', minute: '2-digit'
                                    })
                                    : 'Unknown'
                                  }
                                </div>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>,
              document.body
            )}

            {/* Peak Usage Modal */}
            {showPeakUsageModal && createPortal(
              <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
                {/* Dark/Blurred Overlay */}
                <div
                  className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm transition-opacity"
                  onClick={() => setShowPeakUsageModal(false)}
                ></div>

                {/* Modal Content container */}
                <div className="relative w-full max-w-4xl flex flex-col bg-white rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 fade-in duration-200 z-10">

                  {/* Header */}
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center px-6 py-5 border-b border-gray-100 bg-white gap-4 flex-shrink-0">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-yellow-50 rounded-xl">
                        <Clock className="w-5 h-5 text-yellow-600" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-gray-900 leading-tight">Peak Usage Time</h2>
                        <p className="text-sm text-gray-500">Hourly breakdown of query volume</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 w-full sm:w-auto">
                      {/* Date Filter specifically for Peak Usage */}
                      <div className="flex items-center bg-gray-50 border border-gray-200 rounded-md px-3 py-1.5 shadow-sm transition-colors focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500 w-full sm:w-auto">
                        <Calendar className="w-4 h-4 text-gray-400 mr-2 shrink-0" />
                        <input
                          type="date"
                          value={peakUsageDate}
                          onChange={(e) => {
                            setPeakUsageDate(e.target.value);
                            fetchPeakUsage(e.target.value);
                          }}
                          className="text-sm text-gray-700 outline-none bg-transparent w-full"
                        />
                      </div>

                      {peakUsageLoading && <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full animate-pulse transition-opacity duration-300">Loading...</span>}

                      <button
                        onClick={() => setShowPeakUsageModal(false)}
                        className="text-gray-400 hover:text-gray-600 hover:bg-gray-100 p-2 rounded-full transition-colors flex-shrink-0 focus:outline-none hidden sm:block"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                      </button>
                    </div>
                  </div>

                  {/* Chart Area */}
                  <div className="p-6 bg-gray-50 w-full h-[350px] sm:h-[450px] relative">
                    {peakUsageData?.hourly_data && peakUsageData.hourly_data.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={peakUsageData.hourly_data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                          <defs>
                            <linearGradient id="colorUsage" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#EAB308" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#EAB308" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                          <XAxis
                            dataKey="hour"
                            axisLine={false}
                            tickLine={false}
                            tickMargin={10}
                            tick={{ fill: '#6B7280', fontSize: 12 }}
                            minTickGap={20}
                          />
                          <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#6B7280', fontSize: 12 }}
                            tickMargin={10}
                          />
                          <Tooltip
                            cursor={{ stroke: '#EAB308', strokeWidth: 1, strokeDasharray: '4 4' }}
                            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                            formatter={(value) => [`${value} queries`, 'Volume']}
                            labelFormatter={(label) => `Time: ${label}`}
                          />
                          <Area
                            type="monotone"
                            dataKey="count"
                            stroke="#EAB308"
                            strokeWidth={3}
                            fillOpacity={1}
                            fill="url(#colorUsage)"
                            animationDuration={1000}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400">
                        <Clock className="w-10 h-10 mb-2 opacity-50" />
                        <p>No usage data found for this date.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>,
              document.body
            )}

          </div>
        )}
        {/* --- END TAB CONTENT: Usage & Adoption Insights --- */}

        {/* --- TAB CONTENT: VIN Search Performance --- */}
        {activeTab === 'vin' && (
          <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500">
            {/* KPI Cards for VIN Searches */}
            <div className="grid grid-cols-1 md:grid-cols-1 max-w-sm mx-auto">
              <StatCard
                title="Total VIN Searches"
                value={vinPerformance?.total_searches || 0}
                icon={BarChart2}
                color="purple"
                trend="Click to view user breakdown"
                trendIcon={Users}
                onClick={() => setShowVinUsersModal(true)}
              />

              {/* Overall VIN Success/Failure Rates */}
              {vinPerformance?.total_searches > 0 && (
                <div className="mt-4 flex bg-white border border-gray-100 rounded-2xl overflow-hidden shadow-md">
                  <div className="flex-1 p-6 flex flex-col items-center justify-center border-r border-gray-100 bg-green-50/40">
                    <span className="text-sm font-bold text-green-700 uppercase tracking-wider mb-2">Success Rate</span>
                    <span className="text-4xl font-extrabold text-green-600">
                      {Math.round((vinPerformance.successful_searches / vinPerformance.total_searches) * 100)}%
                    </span>
                  </div>
                  <div className="flex-1 p-6 flex flex-col items-center justify-center bg-red-50/40">
                    <span className="text-sm font-bold text-red-700 uppercase tracking-wider mb-2">Failure Rate</span>
                    <span className="text-4xl font-extrabold text-red-600">
                      {Math.round((vinPerformance.failed_searches / vinPerformance.total_searches) * 100)}%
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Recent Failed VINs Table */}
            {vinPerformance?.recent_failed_vins?.length > 0 && (
              <div className="mt-8">
                <div className="flex items-center gap-2 mb-4 border-b border-gray-100 pb-2">
                  <div className="p-1.5 bg-red-50 rounded-lg text-red-600">
                    <AlertCircle className="w-4 h-4" />
                  </div>
                  <h3 className="text-md font-semibold text-gray-900">Recent Failed VINs</h3>
                </div>
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-hidden">
                  <table className="min-w-full divide-y divide-gray-100">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">User ID</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">VIN</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Time (UAE)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 bg-white">
                      {vinPerformance.recent_failed_vins.map((failure, idx) => (
                        <tr key={idx} className="hover:bg-red-50/50 transition-colors">
                          <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                            +{failure.whatsapp_id}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600 font-mono bg-gray-50/50 rounded inline-block mt-1">
                            {failure.vin}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500">
                            {new Date(failure.timestamp * 1000).toLocaleString('en-US', {
                              timeZone: 'Asia/Dubai',
                              month: 'short', day: 'numeric',
                              hour: '2-digit', minute: '2-digit'
                            })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* VIN Users Modal */}
            {
              showVinUsersModal && createPortal(
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
                  {/* Dark/Blurred Overlay */}
                  <div
                    className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm transition-opacity"
                    onClick={() => setShowVinUsersModal(false)}
                  ></div>

                  {/* Modal Content container */}
                  <div className="relative w-full max-w-3xl max-h-[85vh] flex flex-col bg-white rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 fade-in duration-200 z-10">
                    {/* Header */}
                    <div className="flex justify-between items-center px-6 py-5 border-b border-gray-100 bg-white flex-shrink-0">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-indigo-50 rounded-xl">
                          <Users className="w-5 h-5 text-indigo-600" />
                        </div>
                        <div>
                          <h2 className="text-xl font-bold text-gray-900 leading-tight">VIN Search Breakdown</h2>
                          <p className="text-sm text-gray-500">List of users and their search performance</p>
                        </div>
                      </div>

                      <button
                        onClick={() => setShowVinUsersModal(false)}
                        className="text-gray-400 hover:text-gray-600 hover:bg-gray-100 p-2 rounded-full transition-colors flex-shrink-0 focus:outline-none"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                      </button>
                    </div>

                    {/* Scrollable Content Area */}
                    <div className="overflow-y-auto flex-1 bg-gray-50 custom-scrollbar">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-100 sticky top-0 z-10 shadow-sm">
                          <tr>
                            <th className="px-6 py-3.5 text-left text-xs font-bold text-gray-600 uppercase tracking-wider">
                              Customer Number
                            </th>
                            <th className="px-6 py-3.5 text-left text-xs font-bold text-green-600 uppercase tracking-wider">
                              Success VIN
                            </th>
                            <th className="px-6 py-3.5 text-left text-xs font-bold text-red-600 uppercase tracking-wider">
                              Failed VIN
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-100">
                          {!vinPerformance?.users || vinPerformance.users.length === 0 ? (
                            <tr>
                              <td colSpan="3" className="px-6 py-16 text-center text-sm text-gray-500">
                                <div className="flex flex-col items-center gap-3">
                                  <div className="p-4 bg-gray-100 rounded-full">
                                    <BarChart2 className="w-8 h-8 text-gray-400" />
                                  </div>
                                  <p className="text-base text-gray-600">No VIN search data recorded yet.</p>
                                </div>
                              </td>
                            </tr>
                          ) : (
                            vinPerformance.users.map((u, idx) => (
                              <tr key={idx} className="hover:bg-indigo-50/30 transition-colors">
                                <td className="px-6 py-4 whitespace-nowrap">
                                  <div className="flex items-center">
                                    <div className="h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-sm mr-3">
                                      {idx + 1}
                                    </div>
                                    <span className="text-sm font-medium text-gray-900">
                                      +{u.whatsapp_id}
                                    </span>
                                  </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-green-50 text-green-700 border border-green-100 shadow-sm">
                                    {u.successful_searches}
                                  </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-100 shadow-sm">
                                    {u.failed_searches}
                                  </span>
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>,
                document.body
              )
            }
          </div >
        )}
        {/* --- END TAB CONTENT: VIN Search Performance --- */}

        {/* --- TAB CONTENT: Part Demand Intelligence --- */}
        {
          activeTab === 'parts' && (
            <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Top Part Numbers */}
                <Card className="p-6">
                  <div className="flex items-center gap-2 mb-6 border-b border-gray-100 pb-4">
                    <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
                      <BarChart2 className="w-5 h-5" />
                    </div>
                    <h2 className="text-lg font-semibold text-gray-900">Most Searched Part Numbers</h2>
                  </div>

                  <div className="h-[300px]">
                    {topParts?.top_part_numbers?.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={topParts.top_part_numbers} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#E5E7EB" />
                          <XAxis type="number" hide />
                          <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} width={150} tick={{ fill: '#4B5563', fontSize: 13, fontWeight: 500 }} />
                          <Tooltip cursor={{ fill: '#F3F4F6' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} formatter={(value) => [`${value} searches`, 'Demand']} />
                          <Bar dataKey="count" fill="#4F46E5" radius={[0, 4, 4, 0]} barSize={20} animationDuration={1000} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex items-center justify-center h-full text-gray-500 text-sm">No part numbers recorded yet.</div>
                    )}
                  </div>
                </Card>

                {/* Top Item Descriptions */}
                <Card className="p-6">
                  <div className="flex items-center gap-2 mb-6 border-b border-gray-100 pb-4">
                    <div className="p-2 bg-emerald-50 rounded-lg text-emerald-600">
                      <BarChart2 className="w-5 h-5" />
                    </div>
                    <h2 className="text-lg font-semibold text-gray-900">Most Searched Item Names</h2>
                  </div>

                  <div className="h-[300px]">
                    {topParts?.top_item_descriptions?.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={topParts.top_item_descriptions} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#E5E7EB" />
                          <XAxis type="number" hide />
                          <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} width={150} tick={{ fill: '#4B5563', fontSize: 13, fontWeight: 500 }} />
                          <Tooltip cursor={{ fill: '#F3F4F6' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} formatter={(value) => [`${value} searches`, 'Demand']} />
                          <Bar dataKey="count" fill="#10B981" radius={[0, 4, 4, 0]} barSize={20} animationDuration={1000} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex items-center justify-center h-full text-gray-500 text-sm">No item names recorded yet.</div>
                    )}
                  </div>
                </Card>
              </div>

              {/* User Search Metrics Table */}
              <Card className="p-6">
                <div className="flex items-center gap-2 mb-6 border-b border-gray-100 pb-4">
                  <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                    <Users className="w-5 h-5" />
                  </div>
                  <h2 className="text-lg font-semibold text-gray-900">User Search Activity</h2>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User ID</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Part Numbers Searched</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Item Names Searched</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {topParts?.user_demand_stats?.length > 0 ? (
                        topParts.user_demand_stats.map((user, idx) => (
                          <tr key={idx} className="hover:bg-gray-50 transition-colors">
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              +{user.whatsapp_user_id}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                                {user.part_number_searches}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                                {user.item_description_searches}
                              </span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="3" className="px-6 py-8 text-center text-sm text-gray-500">
                            No user search data available.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </Card>


              {/* Out of Stock Items Table */}
              <Card className="p-6">
                <div className="flex items-center gap-2 mb-6 border-b border-gray-100 pb-4">
                  <div className="p-2 bg-red-50 rounded-lg text-red-600">
                    <AlertCircle className="w-5 h-5" />
                  </div>
                  <h2 className="text-lg font-semibold text-gray-900">Out of Stock Items</h2>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Customer Number</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Out of Stock Part</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Active (UAE)</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {paginatedOosItems.length > 0 ? (
                        paginatedOosItems.map((item, idx) => (
                          <tr key={idx} className="hover:bg-red-50/30 transition-colors">
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              +{item.wp_id}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 font-mono">
                              <div className="flex flex-wrap gap-2">
                                {item.part_numbers && item.part_numbers.map((pn, i) => (
                                  <span key={i} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 border border-red-200 shadow-sm">
                                    {pn}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              <div className="flex items-center text-gray-600">
                                <Calendar className="w-4 h-4 mr-1.5 text-gray-400" />
                                {item.date ? new Date(item.date).toLocaleString('en-US', {
                                  timeZone: 'Asia/Dubai',
                                  year: 'numeric', month: 'short', day: 'numeric',
                                  hour: '2-digit', minute: '2-digit'
                                }) : 'Unknown'}
                              </div>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="3" className="px-6 py-8 text-center text-sm text-gray-500">
                            No out of stock queries recorded yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>

                  {/* Pagination Footer */}
                  {totalOosPages > 1 && (
                    <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between bg-gray-50">
                      <div className="text-sm text-gray-500 font-medium">
                        Showing <span className="text-gray-900">{(oosPage - 1) * OOS_ITEMS_PER_PAGE + 1}</span> to <span className="text-gray-900">{Math.min(oosPage * OOS_ITEMS_PER_PAGE, outOfStockItems.length)}</span> of <span className="text-gray-900">{outOfStockItems.length}</span> items
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setOosPage(prev => Math.max(prev - 1, 1))}
                          disabled={oosPage === 1}
                          className="px-3 py-1 text-sm font-medium border border-gray-300 rounded-lg bg-white hover:bg-gray-50 text-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Previous
                        </button>
                        <button
                          onClick={() => setOosPage(prev => Math.min(prev + 1, totalOosPages))}
                          disabled={oosPage === totalOosPages}
                          className="px-3 py-1 text-sm font-medium border border-gray-300 rounded-lg bg-white hover:bg-gray-50 text-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </Card>


            </div>
          )
        }
        {/* --- END TAB CONTENT: Part Demand Intelligence --- */}

      </div >
    </Layout >
  );
}

function StatCard({ title, value, icon: Icon, color, trend, trendIcon: TrendIcon, onClick }) {
  const colors = {
    purple: 'bg-indigo-50 text-indigo-600 border-indigo-100',
    yellow: 'bg-yellow-50 text-yellow-600 border-yellow-100',
    green: 'bg-emerald-50 text-emerald-600 border-emerald-100',
  };

  return (
    <Card
      className={`p-6 hover:shadow-lg transition-all border ${colors[color] ? colors[color].split(' ')[2] : 'border-gray-100'} group ${onClick ? 'cursor-pointer hover:-translate-y-1' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">{title}</p>
          <p className="text-3xl font-bold mt-2 text-gray-900">{value}</p>
        </div>
        <div className={clsx('p-3 rounded-xl transition-transform group-hover:scale-110', colors[color])}>
          <Icon className="w-6 h-6" />
        </div>
      </div>

      <div className="mt-4 flex items-center text-sm text-gray-500 border-t border-gray-100 pt-4">
        {TrendIcon && <TrendIcon className="w-4 h-4 mr-1 text-gray-400 group-hover:text-primary-500 transition-colors" />}
        <span className="group-hover:text-primary-600 transition-colors">{trend}</span>
      </div>
    </Card>
  );
}

export default Dashboard;
