import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  DailySalesChart,
  CategoryChart,
  RFMChart,
  ForecastChart,
  EvaluatorRadar,
  AnomalyChart,
} from '../components/AnalysisCharts';
import { getLatestRun } from '../api/client';

type TabKey = 'sales' | 'category' | 'anomaly' | 'forecast' | 'rfm' | 'evaluator';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'sales', label: 'Gunluk Satis' },
  { key: 'category', label: 'Kategori' },
  { key: 'anomaly', label: 'Anomaliler' },
  { key: 'forecast', label: 'Tahmin' },
  { key: 'rfm', label: 'RFM' },
  { key: 'evaluator', label: 'Evaluator' },
];

export default function Analytics() {
  const [activeTab, setActiveTab] = useState<TabKey>('sales');
  const [loading, setLoading] = useState(true);
  const [analysis, setAnalysis] = useState<Record<string, unknown>>({});
  const [evaluation, setEvaluation] = useState<Record<string, unknown>>({});
  const [noData, setNoData] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const res = await getLatestRun();
        const run = res.data.run as unknown as Record<string, unknown>;
        const analysisResults = (run?.analysis_results || {}) as Record<string, unknown>;
        const evalData = (run?.evaluation || {}) as Record<string, unknown>;
        setAnalysis(analysisResults);
        setEvaluation(evalData);

        if (Object.keys(analysisResults).length === 0) {
          setNoData(true);
        }
      } catch {
        setNoData(true);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-blue-600" size={32} />
      </div>
    );
  }

  if (noData) {
    return (
      <div className="space-y-6">
        <h2 className="text-xl font-bold text-gray-900">Analizler</h2>
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <p className="text-gray-400">
            Henuz analiz verisi yok. Oncelikle Pipeline sayfasindan bir rapor uretin.
          </p>
        </div>
      </div>
    );
  }

  // Extract data arrays from analysis results
  const dailySales = extractArray(analysis, 'daily_sales', 'trends');
  const categoryPerf = extractArray(analysis, 'category_performance');
  const anomalies = extractArray(analysis, 'anomalies_zscore', 'anomalies_iqr', 'anomalies_isolation_forest');
  const forecast = extractArray(analysis, 'forecast');
  const rfm = extractRFMSegments(analysis);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Analizler</h2>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-4 py-2 text-sm rounded-md transition-colors ${
              activeTab === key
                ? 'bg-white shadow-sm text-gray-900 font-medium'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Chart Area */}
      <div>
        {activeTab === 'sales' && (
          dailySales.length > 0 ? (
            <DailySalesChart data={dailySales as any} />
          ) : (
            <EmptyChart message="Gunluk satis verisi bulunamadi" />
          )
        )}

        {activeTab === 'category' && (
          categoryPerf.length > 0 ? (
            <CategoryChart data={categoryPerf as any} />
          ) : (
            <EmptyChart message="Kategori performans verisi bulunamadi" />
          )
        )}

        {activeTab === 'anomaly' && (
          <div className="space-y-4">
            {anomalies.length > 0 ? (
              <>
                <AnomalyChart data={anomalies as any} />
                <AnomalyTable data={anomalies} />
              </>
            ) : (
              <EmptyChart message="Anomali verisi bulunamadi" />
            )}
          </div>
        )}

        {activeTab === 'forecast' && (
          forecast.length > 0 ? (
            <ForecastChart data={forecast as any} />
          ) : (
            <EmptyChart message="Tahmin verisi bulunamadi" />
          )
        )}

        {activeTab === 'rfm' && (
          rfm.length > 0 ? (
            <RFMChart data={rfm} />
          ) : (
            <EmptyChart message="RFM segmentasyon verisi bulunamadi" />
          )
        )}

        {activeTab === 'evaluator' && (
          Object.keys(evaluation).length > 0 ? (
            <EvaluatorRadar data={evaluation} />
          ) : (
            <EmptyChart message="Evaluator verisi bulunamadi" />
          )
        )}
      </div>
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
      <p className="text-sm text-gray-400">{message}</p>
    </div>
  );
}

function AnomalyTable({ data }: { data: Array<Record<string, unknown>> }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Anomali Detaylari</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left py-2 px-3 text-gray-500 font-medium">Tarih</th>
              <th className="text-left py-2 px-3 text-gray-500 font-medium">Metrik</th>
              <th className="text-right py-2 px-3 text-gray-500 font-medium">Deger</th>
              <th className="text-left py-2 px-3 text-gray-500 font-medium">Yontem</th>
            </tr>
          </thead>
          <tbody>
            {data.slice(0, 20).map((row, i) => (
              <tr key={i} className="border-b border-gray-50">
                <td className="py-2 px-3">{String(row.date || row.order_date || '-')}</td>
                <td className="py-2 px-3">{String(row.column || '-')}</td>
                <td className="py-2 px-3 text-right font-mono">
                  {typeof row.value === 'number' ? row.value.toLocaleString('en-US', { maximumFractionDigits: 2 }) : '-'}
                </td>
                <td className="py-2 px-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    row.method === 'zscore' ? 'bg-red-100 text-red-700' :
                    row.method === 'iqr' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-purple-100 text-purple-700'
                  }`}>
                    {String(row.method || '-')}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Helper: extract arrays from nested analysis results
function extractArray(analysis: Record<string, unknown>, ...keys: string[]): Array<Record<string, unknown>> {
  for (const key of keys) {
    const val = analysis[key];
    if (Array.isArray(val) && val.length > 0) return val;
    if (val && typeof val === 'object' && 'data' in (val as Record<string, unknown>)) {
      const data = (val as Record<string, unknown>).data;
      if (Array.isArray(data)) return data;
    }
  }
  return [];
}

function extractRFMSegments(analysis: Record<string, unknown>): Array<{ segment_label: string; count: number }> {
  const rfm = analysis.rfm_segments || analysis.rfm;
  if (!rfm) return [];

  if (Array.isArray(rfm)) {
    // If it's already segment summary
    if (rfm.length > 0 && 'segment_label' in rfm[0]) {
      return rfm as Array<{ segment_label: string; count: number }>;
    }
    // If it's raw RFM data, group by segment
    const counts: Record<string, number> = {};
    for (const row of rfm) {
      const label = (row as Record<string, unknown>).segment_label as string || 'Unknown';
      counts[label] = (counts[label] || 0) + 1;
    }
    return Object.entries(counts).map(([segment_label, count]) => ({ segment_label, count }));
  }

  if (typeof rfm === 'object' && rfm !== null && 'segments' in (rfm as Record<string, unknown>)) {
    return extractRFMSegments({ rfm_segments: (rfm as Record<string, unknown>).segments });
  }

  return [];
}
