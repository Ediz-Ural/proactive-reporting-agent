import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  DollarSign, TrendingUp, ShoppingCart, Users,
  CheckCircle, XCircle, Database, Brain, Clock,
  FileText, Eye, ArrowUp, ArrowDown, Building2,
} from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import ReportViewer from '../components/ReportViewer';
import { getHealth, getLatestRun, getRuns, getDbStats, getRagStats, getReports, getReport, getCompanyStats } from '../api/client';
import type { CompanyStat } from '../api/client';
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
  const [companyStats, setCompanyStats] = useState<CompanyStat[]>([]);
  const [totals, setTotals] = useState<{
    total_orders: number;
    total_revenue: number;
    total_profit: number;
    total_customers: number;
  } | null>(null);
  const [sortField, setSortField] = useState<keyof CompanyStat>('total_revenue');
  const [sortAsc, setSortAsc] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [healthRes, runsRes, ragRes, csRes] = await Promise.allSettled([
          getHealth(),
          getRuns(10),
          getRagStats(),
          getCompanyStats(),
        ]);

        if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data);
        if (runsRes.status === 'fulfilled') setRuns(runsRes.value.data.runs);
        if (ragRes.status === 'fulfilled') setRagStats(ragRes.value.data);
        if (csRes.status === 'fulfilled') {
          setCompanyStats(csRes.value.data.companies);
          setTotals(csRes.value.data.totals);
        }

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

  const formatCurrency = (v: number): string =>
    '$' + v.toLocaleString('en-US', { maximumFractionDigits: 0 });

  const formatNumber = (v: number): string =>
    v.toLocaleString('en-US');

  const handleSort = (field: keyof CompanyStat) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const sorted = [...companyStats].sort((a, b) => {
    const av = a[sortField];
    const bv = b[sortField];
    if (typeof av === 'number' && typeof bv === 'number') {
      return sortAsc ? av - bv : bv - av;
    }
    return String(av).localeCompare(String(bv)) * (sortAsc ? 1 : -1);
  });

  const maxRevenue = Math.max(...companyStats.map((c) => c.total_revenue), 1);
  const maxProfit = Math.max(...companyStats.map((c) => Math.abs(c.total_profit)), 1);

  const SortIcon = ({ field }: { field: keyof CompanyStat }) => {
    if (sortField !== field) return null;
    return sortAsc ? <ArrowUp size={12} className="inline ml-0.5" /> : <ArrowDown size={12} className="inline ml-0.5" />;
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

      {/* Totals Summary */}
      {totals && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-1">
              <DollarSign size={14} className="text-blue-500" />
              <span className="text-xs text-gray-500">Toplam Gelir</span>
            </div>
            <p className="text-lg font-bold text-gray-900">{formatCurrency(totals.total_revenue)}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp size={14} className="text-green-500" />
              <span className="text-xs text-gray-500">Toplam Kar</span>
            </div>
            <p className="text-lg font-bold text-gray-900">{formatCurrency(totals.total_profit)}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-1">
              <ShoppingCart size={14} className="text-purple-500" />
              <span className="text-xs text-gray-500">Toplam Siparis</span>
            </div>
            <p className="text-lg font-bold text-gray-900">{formatNumber(totals.total_orders)}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-1">
              <Users size={14} className="text-orange-500" />
              <span className="text-xs text-gray-500">Toplam Musteri</span>
            </div>
            <p className="text-lg font-bold text-gray-900">{formatNumber(totals.total_customers)}</p>
          </div>
        </div>
      )}

      {/* Company Comparison Table */}
      {companyStats.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <Building2 size={16} className="text-gray-400" />
            Sirket Karsilastirmasi
            <span className="text-xs font-normal text-gray-400">({companyStats.length} sirket)</span>
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2.5 px-3 text-gray-500 font-medium">#</th>
                  <th className="text-left py-2.5 px-3 text-gray-500 font-medium">Sirket</th>
                  <th
                    className="text-right py-2.5 px-3 text-gray-500 font-medium cursor-pointer hover:text-gray-800 select-none"
                    onClick={() => handleSort('total_revenue')}
                  >
                    Gelir <SortIcon field="total_revenue" />
                  </th>
                  <th
                    className="text-right py-2.5 px-3 text-gray-500 font-medium cursor-pointer hover:text-gray-800 select-none"
                    onClick={() => handleSort('total_profit')}
                  >
                    Kar <SortIcon field="total_profit" />
                  </th>
                  <th
                    className="text-right py-2.5 px-3 text-gray-500 font-medium cursor-pointer hover:text-gray-800 select-none"
                    onClick={() => handleSort('profit_margin_pct')}
                  >
                    Marj % <SortIcon field="profit_margin_pct" />
                  </th>
                  <th
                    className="text-right py-2.5 px-3 text-gray-500 font-medium cursor-pointer hover:text-gray-800 select-none"
                    onClick={() => handleSort('total_orders')}
                  >
                    Siparis <SortIcon field="total_orders" />
                  </th>
                  <th
                    className="text-right py-2.5 px-3 text-gray-500 font-medium cursor-pointer hover:text-gray-800 select-none"
                    onClick={() => handleSort('unique_customers')}
                  >
                    Musteri <SortIcon field="unique_customers" />
                  </th>
                  <th
                    className="text-right py-2.5 px-3 text-gray-500 font-medium cursor-pointer hover:text-gray-800 select-none"
                    onClick={() => handleSort('avg_order_value')}
                  >
                    Ort. Siparis <SortIcon field="avg_order_value" />
                  </th>
                  <th className="text-left py-2.5 px-3 text-gray-500 font-medium w-36">Gelir Payi</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((c, i) => (
                  <tr key={c.company_id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2.5 px-3 text-gray-400 text-xs">{i + 1}</td>
                    <td className="py-2.5 px-3 font-medium text-gray-800">{c.company_name}</td>
                    <td className="py-2.5 px-3 text-right font-medium">{formatCurrency(c.total_revenue)}</td>
                    <td className={`py-2.5 px-3 text-right font-medium ${c.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatCurrency(c.total_profit)}
                    </td>
                    <td className={`py-2.5 px-3 text-right ${c.profit_margin_pct >= 10 ? 'text-green-600' : c.profit_margin_pct >= 0 ? 'text-yellow-600' : 'text-red-600'}`}>
                      {c.profit_margin_pct.toFixed(1)}%
                    </td>
                    <td className="py-2.5 px-3 text-right">{formatNumber(c.total_orders)}</td>
                    <td className="py-2.5 px-3 text-right">{formatNumber(c.unique_customers)}</td>
                    <td className="py-2.5 px-3 text-right">${c.avg_order_value.toFixed(0)}</td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${(c.total_revenue / maxRevenue) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-400 w-10 text-right">
                          {totals ? ((c.total_revenue / totals.total_revenue) * 100).toFixed(1) : 0}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Profit Margin Ranking - Visual Bar Chart */}
      {companyStats.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Kar Performansi</h3>
          <div className="space-y-2">
            {[...companyStats]
              .sort((a, b) => b.total_profit - a.total_profit)
              .map((c) => (
                <div key={c.company_id} className="flex items-center gap-3">
                  <span className="text-xs text-gray-600 w-40 truncate">{c.company_name}</span>
                  <div className="flex-1 flex items-center">
                    {c.total_profit >= 0 ? (
                      <div className="w-1/2 flex justify-end pr-1">
                        <div className="h-4" />
                      </div>
                    ) : (
                      <div className="w-1/2 flex justify-end pr-1">
                        <div
                          className="h-4 bg-red-400 rounded-l"
                          style={{ width: `${(Math.abs(c.total_profit) / maxProfit) * 100}%` }}
                        />
                      </div>
                    )}
                    {c.total_profit >= 0 ? (
                      <div className="w-1/2 pl-1">
                        <div
                          className="h-4 bg-green-400 rounded-r"
                          style={{ width: `${(c.total_profit / maxProfit) * 100}%` }}
                        />
                      </div>
                    ) : (
                      <div className="w-1/2 pl-1">
                        <div className="h-4" />
                      </div>
                    )}
                  </div>
                  <span className={`text-xs font-medium w-20 text-right ${c.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {formatCurrency(c.total_profit)}
                  </span>
                </div>
              ))}
            <div className="flex items-center gap-3 mt-1">
              <span className="w-40" />
              <div className="flex-1 border-t border-gray-200 relative">
                <span className="absolute left-1/2 -translate-x-1/2 -top-2.5 text-[10px] text-gray-400 bg-white px-1">$0</span>
              </div>
              <span className="w-20" />
            </div>
          </div>
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
