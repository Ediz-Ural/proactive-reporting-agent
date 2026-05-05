import { useState, useEffect } from 'react';
import { uploadData, getCompanies } from '../../api/client';
import { Upload, CheckCircle, AlertCircle } from 'lucide-react';

export default function UploadData() {
  const [file, setFile] = useState<File | null>(null);
  const [companyId, setCompanyId] = useState<number | undefined>(undefined);
  const [companies, setCompanies] = useState<Array<{ id: number; name: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ message: string; new_rows: number } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    getCompanies()
      .then(res => setCompanies(res.data.companies as Array<{ id: number; name: string }>))
      .catch(() => {});
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const res = await uploadData(file, companyId);
      setResult(res.data);
      setFile(null);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 mb-6">Veri Yukle (CSV)</h2>

      <div className="bg-white rounded-lg shadow p-6 max-w-lg">
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Sirket</label>
          <select
            value={companyId ?? ''}
            onChange={e => setCompanyId(e.target.value ? Number(e.target.value) : undefined)}
            className="w-full border rounded px-3 py-2 text-sm"
          >
            <option value="">Mevcut sirketim</option>
            {companies.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">CSV Dosyasi</label>
          <input
            type="file"
            accept=".csv"
            onChange={e => setFile(e.target.files?.[0] || null)}
            className="w-full text-sm"
          />
          <p className="text-xs text-gray-500 mt-1">
            Gerekli kolonlar: order_id, order_date, sales, quantity, profit
          </p>
        </div>

        <button
          onClick={handleUpload}
          disabled={!file || loading}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          <Upload size={16} />
          {loading ? 'Yukleniyor...' : 'Yukle'}
        </button>

        {result && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded p-3 flex items-start gap-2">
            <CheckCircle size={18} className="text-green-600 mt-0.5 shrink-0" />
            <div className="text-sm text-green-800">
              <p className="font-medium">{result.message}</p>
              <p>{result.new_rows} yeni satir eklendi</p>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded p-3 flex items-start gap-2">
            <AlertCircle size={18} className="text-red-600 mt-0.5 shrink-0" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
