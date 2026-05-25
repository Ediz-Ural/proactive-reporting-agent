import { useEffect, useState, useMemo } from 'react';
import { FileText, Download, Eye, Filter, Building2, Mail, CheckCircle, XCircle } from 'lucide-react';
import ReportViewer from '../components/ReportViewer';
import { getReports, getReport, getCompanies, sendReportEmail } from '../api/client';
import type { ReportFile } from '../types';

interface CompanyOption {
  id: number;
  name: string;
}

export default function Reports() {
  const [reports, setReports] = useState<ReportFile[]>([]);
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState<{
    filename: string;
    company_id: number;
    content_md: string;
    content_html: string | null;
  } | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | 0>(0);
  const [emailSending, setEmailSending] = useState(false);
  const [emailStatus, setEmailStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem('user') || '{}');
    } catch {
      return {};
    }
  }, []);

  const isAdmin = user.role === 'admin';

  useEffect(() => {
    async function load() {
      try {
        const res = await getReports();
        setReports(res.data.reports);

        if (isAdmin) {
          try {
            const cRes = await getCompanies();
            const list = (cRes.data.companies || []).map((c: Record<string, unknown>) => ({
              id: c.id as number,
              name: c.name as string,
            }));
            setCompanies(list);
          } catch {
            // derive from reports
            const ids = new Map<number, string>();
            for (const r of res.data.reports) {
              if (!ids.has(r.company_id)) {
                const name = r.filename.replace(/_\d{4}-\d{2}-\d{2}.*$/, '').replace(/_/g, ' ');
                ids.set(r.company_id, name);
              }
            }
            setCompanies(Array.from(ids.entries()).map(([id, name]) => ({ id, name })).sort((a, b) => a.id - b.id));
          }
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [isAdmin]);

  async function handleView(filename: string, companyId: number) {
    setViewLoading(true);
    try {
      const res = await getReport(filename, isAdmin ? companyId : undefined);
      setSelectedReport(res.data);
    } catch {
      // ignore
    } finally {
      setViewLoading(false);
    }
  }

  function handleDownload(content: string, filename: string) {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleSendEmail() {
    if (!selectedReport) return;
    setEmailSending(true);
    setEmailStatus(null);
    try {
      const res = await sendReportEmail({
        report_filename: selectedReport.filename,
        company_id: selectedReport.company_id,
        recipients: [],
      });
      setEmailStatus({
        type: 'success',
        message: res.data.message || 'Email gonderildi',
      });
    } catch (err: unknown) {
      let message = 'Email gonderilemedi';
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { detail?: string } } };
        message = axErr.response?.data?.detail || message;
      }
      setEmailStatus({ type: 'error', message });
    } finally {
      setEmailSending(false);
    }
  }

  function getCompanyName(companyId: number): string {
    const c = companies.find((co) => co.id === companyId);
    return c ? c.name : `Sirket #${companyId}`;
  }

  function extractPeriod(filename: string): string {
    const match = filename.match(/(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})/);
    if (!match) return '';
    return `${match[1]} — ${match[2]}`;
  }

  const filteredReports = useMemo(() => {
    let list = reports;
    if (selectedCompanyId > 0) {
      list = list.filter((r) => r.company_id === selectedCompanyId);
    }
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (r) =>
          r.filename.toLowerCase().includes(q) ||
          getCompanyName(r.company_id).toLowerCase().includes(q)
      );
    }
    return list;
  }, [reports, selectedCompanyId, search, companies]);

  const reportsByCompany = useMemo(() => {
    const grouped = new Map<number, ReportFile[]>();
    for (const r of filteredReports) {
      if (!grouped.has(r.company_id)) grouped.set(r.company_id, []);
      grouped.get(r.company_id)!.push(r);
    }
    return grouped;
  }, [filteredReports]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">Raporlar</h2>
        <span className="text-sm text-gray-500">{filteredReports.length} rapor</span>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <input
            type="text"
            placeholder="Rapor ara..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pl-10"
          />
          <FileText size={16} className="absolute left-3 top-3 text-gray-400" />
        </div>

        {isAdmin && companies.length > 0 && (
          <div className="relative">
            <select
              value={selectedCompanyId}
              onChange={(e) => setSelectedCompanyId(Number(e.target.value))}
              className="appearance-none w-full sm:w-64 px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pl-10 pr-8 bg-white"
            >
              <option value={0}>Tum Sirketler</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <Building2 size={16} className="absolute left-3 top-3 text-gray-400 pointer-events-none" />
            <Filter size={14} className="absolute right-3 top-3.5 text-gray-400 pointer-events-none" />
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Report List */}
        <div className="space-y-4 max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
          {filteredReports.length > 0 ? (
            selectedCompanyId > 0 ? (
              // Single company — flat list
              <div className="space-y-2">
                {filteredReports.map((r) => (
                  <ReportCard
                    key={`${r.company_id}-${r.filename}`}
                    report={r}
                    isSelected={selectedReport?.filename === r.filename && selectedReport?.company_id === r.company_id}
                    period={extractPeriod(r.filename)}
                    onView={() => handleView(r.filename, r.company_id)}
                  />
                ))}
              </div>
            ) : (
              // All companies — grouped
              Array.from(reportsByCompany.entries())
                .sort(([a], [b]) => a - b)
                .map(([cid, cReports]) => (
                  <div key={cid}>
                    <div className="flex items-center gap-2 mb-2 px-1">
                      <Building2 size={14} className="text-blue-600" />
                      <h3 className="text-sm font-semibold text-gray-700">
                        {getCompanyName(cid)}
                      </h3>
                      <span className="text-xs text-gray-400">({cReports.length} rapor)</span>
                    </div>
                    <div className="space-y-1.5">
                      {cReports.map((r) => (
                        <ReportCard
                          key={`${r.company_id}-${r.filename}`}
                          report={r}
                          isSelected={selectedReport?.filename === r.filename && selectedReport?.company_id === r.company_id}
                          period={extractPeriod(r.filename)}
                          onView={() => handleView(r.filename, r.company_id)}
                        />
                      ))}
                    </div>
                  </div>
                ))
            )
          ) : (
            <p className="text-sm text-gray-400 text-center py-8">Rapor bulunamadi.</p>
          )}
        </div>

        {/* Report Viewer */}
        <div className="lg:sticky lg:top-4">
          {viewLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          ) : selectedReport ? (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <h3 className="text-sm font-semibold text-gray-700 flex-1 truncate">
                  {selectedReport.filename}
                </h3>
                <button
                  onClick={() => handleDownload(selectedReport.content_md, selectedReport.filename)}
                  className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded transition-colors"
                >
                  <Download size={12} /> MD
                </button>
                {selectedReport.content_html && (
                  <button
                    onClick={() =>
                      handleDownload(
                        selectedReport.content_html!,
                        selectedReport.filename.replace('.md', '.html')
                      )
                    }
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded transition-colors"
                  >
                    <Download size={12} /> HTML
                  </button>
                )}
                {isAdmin && (
                  <button
                    onClick={handleSendEmail}
                    disabled={emailSending}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 rounded transition-colors"
                  >
                    <Mail size={12} />
                    {emailSending ? 'Gonderiliyor...' : 'Email Gonder'}
                  </button>
                )}
              </div>
              {emailStatus && (
                <div className={`flex items-center gap-2 mb-2 px-3 py-2 rounded-lg text-xs ${
                  emailStatus.type === 'success'
                    ? 'bg-green-50 text-green-700 border border-green-200'
                    : 'bg-red-50 text-red-700 border border-red-200'
                }`}>
                  {emailStatus.type === 'success' ? <CheckCircle size={14} /> : <XCircle size={14} />}
                  {emailStatus.message}
                </div>
              )}
              <ReportViewer
                contentMd={selectedReport.content_md}
                contentHtml={selectedReport.content_html}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 bg-white rounded-xl border border-gray-200">
              <p className="text-sm text-gray-400">Bir rapor secin</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ReportCard({
  report,
  isSelected,
  period,
  onView,
}: {
  report: ReportFile;
  isSelected: boolean;
  period: string;
  onView: () => void;
}) {
  return (
    <div
      className={`bg-white rounded-lg border p-3 cursor-pointer transition-colors ${
        isSelected
          ? 'border-blue-500 bg-blue-50'
          : 'border-gray-200 hover:border-gray-300'
      }`}
      onClick={onView}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <FileText size={14} className="text-gray-400 shrink-0" />
          <span className="text-sm font-medium text-gray-900 truncate">
            {period || report.filename}
          </span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onView();
          }}
          className="p-1.5 hover:bg-gray-100 rounded shrink-0"
          title="Goruntule"
        >
          <Eye size={14} className="text-gray-500" />
        </button>
      </div>
      <div className="mt-1 flex items-center gap-3 text-xs text-gray-400">
        <span>{(report.size_bytes / 1024).toFixed(1)} KB</span>
        {report.has_html && <span className="text-green-600">HTML</span>}
      </div>
    </div>
  );
}
