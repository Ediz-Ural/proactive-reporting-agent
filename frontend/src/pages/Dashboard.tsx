import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  DollarSign, TrendingUp, ShoppingCart, Users,
  CheckCircle, XCircle, Database, Brain, Clock,
} from 'lucide-react';
import KPICard from '../components/KPICard';
import StatusBadge from '../components/StatusBadge';
import { getHealth, getLatestRun, getRuns, getDbStats, getRagStats } from '../api/client';
import type { HealthStatus, PipelineRun, RagStats } from '../types';

export default function Dashboard() {
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

  // Extract KPI data from latest run if available
  const summary = (latestRun?.run as unknown as Record<string, unknown>)?.weekly_summary as Record<string, number> | undefined;

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
          value={summary?.total_revenue ? `$${summary.total_revenue.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '-'}
          icon={DollarSign}
          change={summary?.growth_rate_pct as number | undefined}
        />
        <KPICard
          title="Toplam Kar"
          value={summary?.total_profit ? `$${summary.total_profit.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '-'}
          icon={TrendingUp}
        />
        <KPICard
          title="Siparis Sayisi"
          value={summary?.total_orders || '-'}
          icon={ShoppingCart}
        />
        <KPICard
          title="Musteri Sayisi"
          value={summary?.unique_customers || '-'}
          icon={Users}
        />
      </div>

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
                  label={ragStats?.status === 'ok' ? 'Aktif' : 'Kapalı'}
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
