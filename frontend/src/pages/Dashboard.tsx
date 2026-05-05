import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  DollarSign, TrendingUp, ShoppingCart, Users,
  CheckCircle, XCircle, Database, Brain, Clock,
  FileText, Eye,
} from 'lucide-react';
import KPICard from '../components/KPICard';
import StatusBadge from '../components/StatusBadge';
import ReportViewer from '../components/ReportViewer';
import { getHealth, getLatestRun, getRuns, getDbStats, getRagStats, getReports, getReport } from '../api/client';
import type { HealthStatus, PipelineRun, RagStats, ReportFile } from '../types';

function UserDashboard() {
  const [reports, setReports] = useState<ReportFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedReport, setSelectedReport] = useState<{
    filename: string;
    content_md: string;
    content_html: string | null;
  } | null>(null);
  const [viewLoading, setViewLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const res = await getReports();
        setReports(res.data.reports);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleView(filename: string) {
    setViewLoading(true);
    try {
      const res = await getReport(filename);
      setSelectedReport(res.data);
    } catch {
      // ignore
    } finally {
      setViewLoading(false);
    }
  }

  const formatDate = (ts: number) =>
    new Date(ts * 1000).toLocaleDateString('tr-TR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });

  const filteredReports = reports.filter((r) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    const dateStr = formatDate(r.created_at).toLowerCase();
    const fname = r.filename.toLowerCase();
    return dateStr.includes(q) || fname.includes(q);
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Dashboard</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Report List */}
        <div className="lg:col-span-1 space-y-3">
          {/* Search */}
          <div className="relative">
            <input
              type="text"
              placeholder="Tarih veya rapor ara... (ör: Ocak 2017)"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pl-10 bg-white"
            />
            <FileText size={16} className="absolute left-3 top-3 text-gray-400" />
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
              <FileText size={16} className="text-gray-400" />
              Son Raporlar
              {search && (
                <span className="text-xs font-normal text-gray-400">
                  ({filteredReports.length} sonuc)
                </span>
              )}
            </h3>
            {filteredReports.length > 0 ? (
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {filteredReports.map((r) => (
                  <button
                    key={r.filename}
                    onClick={() => handleView(r.filename)}
                    className={`w-full text-left p-3 rounded-lg border transition-colors ${
                      selectedReport?.filename === r.filename
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-100 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <FileText size={14} className="text-gray-400 shrink-0" />
                      <span className="text-sm font-medium text-gray-800 truncate">
                        {r.filename.replace('.md', '')}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1 ml-6">
                      {formatDate(r.created_at)}
                    </p>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400 text-center py-8">
                {search ? 'Aramayla eslesen rapor bulunamadi.' : 'Henuz rapor bulunmuyor.'}
              </p>
            )}
          </div>
        </div>

        {/* Report Viewer */}
        <div className="lg:col-span-2">
          {viewLoading ? (
            <div className="flex items-center justify-center h-64 bg-white rounded-xl border border-gray-200">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          ) : selectedReport ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                {selectedReport.filename.replace('.md', '')}
              </h3>
              <ReportViewer
                contentMd={selectedReport.content_md}
                contentHtml={selectedReport.content_html}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 bg-white rounded-xl border border-gray-200">
              <div className="text-center">
                <Eye size={32} className="text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-400">Goruntulemek icin bir rapor secin</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AdminDashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [latestRun, setLatestRun] = useState<{
    run: PipelineRun;
    report_content: string | null;
  } | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [dbTotal, setDbTotal] = useState<number>(0);
  const [ragStats, setRagStats] = useState<RagStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [healthRes, runsRes, ragRes] = await Promise.allSettled([
          getHealth(),
          getRuns(10),
          getRagStats(),
        ]);

        if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data);
        if (runsRes.status === 'fulfilled') setRuns(runsRes.value.data.runs);
        if (ragRes.status === 'fulfilled') setRagStats(ragRes.value.data);

        try {
          const latestRes = await getLatestRun();
          setLatestRun(latestRes.data);
        } catch {
          // No runs yet
        }

        try {
          const dbRes = await getDbStats();
          setDbTotal(dbRes.data.total_orders);
        } catch {
          // DB stats unavailable
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  const summary = latestRun?.run.weekly_summary;
  const comparison = latestRun?.run.period_comparison;

  const formatCurrency = (v: number | undefined): string => {
    if (v === undefined || v === null) return '-';
    return new Intl.NumberFormat('tr-TR', {
      style: 'currency',
      currency: 'TRY',
      maximumFractionDigits: 0,
    }).format(v);
  };

  const formatNumber = (v: number | undefined): string => {
    if (v === undefined || v === null) return '-';
    return new Intl.NumberFormat('tr-TR').format(v);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">Dashboard</h2>
        <StatusBadge
          status={health?.status === 'ok' ? 'ok' : 'degraded'}
          label={health?.status === 'ok' ? 'Sistem Aktif' : 'Sorun Var'}
        />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Toplam Gelir"
          value={formatCurrency(summary?.total_revenue)}
          icon={DollarSign}
          change={comparison?.total_sales_change_pct}
        />
        <KPICard
          title="Toplam Kar"
          value={formatCurrency(summary?.total_profit)}
          icon={TrendingUp}
          change={comparison?.total_profit_change_pct}
        />
        <KPICard
          title="Siparis Sayisi"
          value={formatNumber(summary?.total_orders)}
          icon={ShoppingCart}
          change={comparison?.total_orders_change_pct}
        />
        <KPICard
          title="Musteri Sayisi"
          value={formatNumber(summary?.unique_customers)}
          icon={Users}
        />
      </div>

      {!latestRun && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-700">
          Henuz rapor uretilmemis. Ilk raporu uretmek icin Pipeline sayfasina gidin.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latest Report */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Son Rapor</h3>
          {latestRun ? (
            <div>
              <p className="text-sm text-gray-600 mb-2">
                {latestRun.run.period || latestRun.run.report_type || 'N/A'}
              </p>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-sm">
                  Skor: <strong>{latestRun.run.quality_score?.toFixed(2) || 'N/A'}</strong>
                </span>
                {latestRun.run.quality_score >= 0.7 ? (
                  <CheckCircle size={16} className="text-green-500" />
                ) : (
                  <XCircle size={16} className="text-red-500" />
                )}
                <span className="text-xs text-gray-400">
                  {latestRun.run.evaluator_iterations || 1} iterasyon
                </span>
              </div>
              <Link
                to="/reports"
                className="text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                Raporu Goruntule &rarr;
              </Link>
            </div>
          ) : (
            <p className="text-sm text-gray-400">Henuz rapor uretilmedi.</p>
          )}
        </div>

        {/* System Status */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Sistem Durumu</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database size={16} className="text-gray-400" />
                <span className="text-sm">Veritabani</span>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge
                  status={health?.database.connected ? 'ok' : 'error'}
                  label={health?.database.db_type || 'N/A'}
                />
                <span className="text-xs text-gray-400">
                  {dbTotal > 0 ? `${dbTotal.toLocaleString()} kayit` : ''}
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain size={16} className="text-gray-400" />
                <span className="text-sm">RAG (ChromaDB)</span>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge
                  status={ragStats?.status === 'ok' ? 'ok' : 'error'}
                  label={ragStats?.status === 'ok' ? 'Aktif' : 'Kapali'}
                />
                {ragStats?.total_chunks && (
                  <span className="text-xs text-gray-400">
                    {ragStats.total_chunks} chunk
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock size={16} className="text-gray-400" />
                <span className="text-sm">Scheduler</span>
              </div>
              <StatusBadge
                status={health?.scheduler_enabled ? 'ok' : 'error'}
                label={health?.scheduler_enabled ? 'Aktif' : 'Devre Disi'}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Recent Runs */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Son Pipeline Calismalari</h3>
        {runs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Run ID</th>
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Donem</th>
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Tip</th>
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Skor</th>
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Durum</th>
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Zaman</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.run_id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-3 font-mono text-xs">{run.run_id?.slice(0, 8)}...</td>
                    <td className="py-2 px-3">{run.period || '-'}</td>
                    <td className="py-2 px-3">{run.report_type || '-'}</td>
                    <td className="py-2 px-3">
                      <span className={`font-medium ${
                        run.quality_score >= 0.7 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {run.quality_score?.toFixed(2) || 'N/A'}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      <StatusBadge
                        status={run.error_count > 0 ? 'error' : 'completed'}
                        label={run.error_count > 0 ? 'Hata' : 'Basarili'}
                      />
                    </td>
                    <td className="py-2 px-3 text-xs text-gray-400">{run.timestamp || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400">Henuz pipeline calismasi yok.</p>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const isAdmin = user.role === 'admin';

  return isAdmin ? <AdminDashboard /> : <UserDashboard />;
}
