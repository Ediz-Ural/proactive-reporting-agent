import { useState, useEffect } from 'react';
import { getCompanies, createCompany } from '../../api/client';
import { Building2, Plus } from 'lucide-react';

interface Company {
  id: number;
  name: string;
  slug: string;
  email_domain: string;
  created_at: string;
  is_active: boolean | number;
}

export default function Companies() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [emailDomain, setEmailDomain] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchCompanies = () => {
    getCompanies()
      .then(res => setCompanies(res.data.companies as Company[]))
      .catch(() => {});
  };

  useEffect(() => { fetchCompanies(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await createCompany({ name, slug, email_domain: emailDomain });
      setName('');
      setSlug('');
      setEmailDomain('');
      setShowForm(false);
      fetchCompanies();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Creation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">Sirketler</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700"
        >
          <Plus size={16} />
          Yeni Sirket
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow p-4 mb-6 max-w-lg">
          <form onSubmit={handleCreate} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">Ad</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full border rounded px-3 py-1.5 text-sm mt-1"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Slug</label>
              <input
                value={slug}
                onChange={e => setSlug(e.target.value)}
                className="w-full border rounded px-3 py-1.5 text-sm mt-1"
                placeholder="sirket-adi"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Email Domain</label>
              <input
                value={emailDomain}
                onChange={e => setEmailDomain(e.target.value)}
                className="w-full border rounded px-3 py-1.5 text-sm mt-1"
                placeholder="example.com"
              />
            </div>
            {error && <p className="text-red-600 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Olusturuluyor...' : 'Olustur'}
            </button>
          </form>
        </div>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Ad</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Slug</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Email Domain</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Durum</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {companies.map(c => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-500">{c.id}</td>
                <td className="px-4 py-3 font-medium text-gray-800 flex items-center gap-2">
                  <Building2 size={16} className="text-gray-400" />
                  {c.name}
                </td>
                <td className="px-4 py-3 text-gray-600">{c.slug}</td>
                <td className="px-4 py-3 text-gray-600">{c.email_domain || '-'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    c.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {c.is_active ? 'Aktif' : 'Pasif'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {companies.length === 0 && (
          <p className="text-center text-gray-500 py-8 text-sm">Henuz sirket yok</p>
        )}
      </div>
    </div>
  );
}
