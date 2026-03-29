import { useEffect, useState } from 'react';
import { FileText, Download, Eye } from 'lucide-react';
import ReportViewer from '../components/ReportViewer';
import { getReports, getReport } from '../api/client';
import type { ReportFile } from '../types';

export default function Reports() {
  const [reports, setReports] = useState<ReportFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState<{
    filename: string;
    content_md: string;
    content_html: string | null;
  } | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [search, setSearch] = useState('');

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

  function handleDownload(content: string, filename: string) {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  const filteredReports = reports.filter((r) =>
    r.filename.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Raporlar</h2>

      {/* Search */}
      <div className="relative">
        <input
          type="text"
          placeholder="Rapor ara..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pl-10"
        />
        <FileText size={16} className="absolute left-3 top-3 text-gray-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Report List */}
        <div className="space-y-2">
          {filteredReports.length > 0 ? (
            filteredReports.map((r) => (
              <div
                key={r.filename}
                className={`bg-white rounded-lg border p-4 cursor-pointer transition-colors ${
                  selectedReport?.filename === r.filename
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
                onClick={() => handleView(r.filename)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText size={16} className="text-gray-400" />
                    <span className="text-sm font-medium text-gray-900">{r.filename}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleView(r.filename); }}
                      className="p-1.5 hover:bg-gray-100 rounded"
                      title="Goruntule"
                    >
                      <Eye size={14} className="text-gray-500" />
                    </button>
                  </div>
                </div>
                <div className="mt-1 flex items-center gap-3 text-xs text-gray-400">
                  <span>{new Date(r.created_at * 1000).toLocaleString('tr-TR')}</span>
                  <span>{(r.size_bytes / 1024).toFixed(1)} KB</span>
                  {r.has_html && <span className="text-green-600">HTML</span>}
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-gray-400 text-center py-8">Rapor bulunamadi.</p>
          )}
        </div>

        {/* Report Viewer */}
        <div>
          {viewLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          ) : selectedReport ? (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <h3 className="text-sm font-semibold text-gray-700 flex-1">
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
              </div>
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
