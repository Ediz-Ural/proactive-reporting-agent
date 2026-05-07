import { useState, useEffect } from 'react';
import { Play, Calendar, Building2 } from 'lucide-react';
import PipelineProgress from '../components/PipelineProgress';
import ReportViewer from '../components/ReportViewer';
import { EvaluatorRadar } from '../components/AnalysisCharts';
import { runPipeline, runMonthly, getCompanies } from '../api/client';
import type { PipelineResult } from '../types';

function formatLocalDate(d: Date): string {
  const yy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yy}-${mm}-${dd}`;
}

function computeDateRange(start: string, type: string): { start: string; end: string } {
  const parts = start.split('-').map(Number);
  const y = parts[0], m = parts[1], d = parts[2];
  if (!y || !m || !d || isNaN(y) || isNaN(m) || isNaN(d)) {
    return { start, end: start };
  }
  try {
    if (type === 'quarterly') {
      return { start, end: formatLocalDate(new Date(y, m + 2, 0)) };
    }
    if (type === 'weekly') {
      return { start, end: formatLocalDate(new Date(y, m - 1, d + 6)) };
    }
    return { start, end: formatLocalDate(new Date(y, m, 0)) };
  } catch {
    return { start, end: start };
  }
}

export default function Pipeline() {
  const [startDate, setStartDate] = useState('2017-01-01');
  const [reportType, setReportType] = useState('monthly');
  const [companyId, setCompanyId] = useState<number>(1);
  const [companies, setCompanies] = useState<Array<{ id: number; name: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<'idle' | 'running' | 'completed' | 'error'>('idle');

  const { start: computedStart, end: computedEnd } = computeDateRange(startDate, reportType);

  useEffect(() => {
    async function loadCompanies() {
      try {
        const res = await getCompanies();
        setCompanies(res.data.companies as Array<{ id: number; name: string }>);
      } catch {
        // ignore
      }
    }
    loadCompanies();
  }, []);

  async function handleRun() {
    setLoading(true);
    setError(null);
    setResult(null);
    setPipelineStatus('running');

    try {
      const res = await runPipeline({
        start_date: computedStart,
        end_date: computedEnd,
        report_type: reportType,
        company_id: companyId,
      });
      setResult(res.data);
      if (res.data.status === 'quality_failed') {
        setError(res.data.errors?.join(', ') || 'Kalite kontrolu basarisiz');
        setPipelineStatus('error');
      } else {
        setPipelineStatus('completed');
      }
    } catch (err: unknown) {
      let message = 'Pipeline hatasi';
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { detail?: string } } };
        message = axErr.response?.data?.detail || message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
      setPipelineStatus('error');
    } finally {
      setLoading(false);
    }
  }

  async function handleMonthly() {
    setLoading(true);
    setError(null);
    setPipelineStatus('running');

    try {
      await runMonthly();
      setPipelineStatus('completed');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Pipeline hatasi';
      setError(message);
      setPipelineStatus('error');
    } finally {
      setLoading(false);
    }
  }

  const selectedCompanyName = companies.find(c => c.id === companyId)?.name || '';

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Pipeline</h2>

      {/* Input Form */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Rapor Uret</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              <Building2 size={12} className="inline mr-1" />
              Sirket
            </label>
            <select
              value={companyId}
              onChange={(e) => setCompanyId(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Baslangic Tarihi</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Donem: {computedStart} &mdash; {computedEnd}
            </p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Rapor Tipi</label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="weekly">Haftalik</option>
              <option value="monthly">Aylik</option>
              <option value="quarterly">Ceyreklik</option>
            </select>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRun}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Play size={16} />
            {loading ? 'Calisiyor...' : "Pipeline'i Baslat"}
          </button>
          <button
            onClick={handleMonthly}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2.5 bg-gray-800 text-white rounded-lg text-sm font-medium hover:bg-gray-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Calendar size={16} />
            Aylik Rapor Uret
          </button>
          {selectedCompanyName && (
            <span className="text-xs text-gray-400">
              {selectedCompanyName} icin rapor uretilecek
            </span>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Progress */}
      <PipelineProgress status={pipelineStatus} />

      {/* Result */}
      {result && (
        <div className="space-y-6">
          {/* Summary KPIs */}
          {result.weekly_summary && Object.keys(result.weekly_summary).length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Ozet Gostergeler</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-gray-500">Gelir</p>
                  <p className="text-lg font-bold">${result.weekly_summary.total_revenue?.toLocaleString('en-US', { maximumFractionDigits: 2 })}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Kar</p>
                  <p className="text-lg font-bold">${result.weekly_summary.total_profit?.toLocaleString('en-US', { maximumFractionDigits: 2 })}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Siparisler</p>
                  <p className="text-lg font-bold">{result.weekly_summary.total_orders}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Musteriler</p>
                  <p className="text-lg font-bold">{result.weekly_summary.unique_customers}</p>
                </div>
              </div>
            </div>
          )}

          {/* Evaluator Scores */}
          {result.evaluation && Object.keys(result.evaluation).length > 0 && (
            <EvaluatorRadar data={result.evaluation} />
          )}

          {/* Generated Report */}
          {result.draft_report && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Uretilen Rapor</h3>
              <ReportViewer contentMd={result.draft_report} />
            </div>
          )}

          {/* Errors */}
          {result.errors && result.errors.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-yellow-800 mb-2">Uyarilar</h3>
              <ul className="text-sm text-yellow-700 space-y-1">
                {result.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
