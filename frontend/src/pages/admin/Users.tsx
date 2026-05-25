import { useState, useEffect } from 'react';
import { getUsers, getCompanies, registerUser } from '../../api/client';
import { UserPlus } from 'lucide-react';

interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  company_id: number;
  company_name: string;
  created_at: string;
  is_active: boolean | number;
}

export default function Users() {
  const [users, setUsers] = useState<User[]>([]);
  const [companies, setCompanies] = useState<Array<{ id: number; name: string }>>([]);
  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [companyId, setCompanyId] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchUsers = () => {
    getUsers()
      .then(res => setUsers(res.data.users as unknown as User[]))
      .catch(() => {});
  };

  useEffect(() => {
    fetchUsers();
    getCompanies()
      .then(res => setCompanies(res.data.companies as Array<{ id: number; name: string }>))
      .catch(() => {});
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await registerUser({ email, password, full_name: fullName, company_id: companyId });
      setEmail('');
      setPassword('');
      setFullName('');
      setShowForm(false);
      fetchUsers();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">Kullanicilar</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700"
        >
          <UserPlus size={16} />
          Yeni Kullanici
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow p-4 mb-6 max-w-lg">
          <form onSubmit={handleCreate} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">Ad Soyad</label>
              <input
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                className="w-full border rounded px-3 py-1.5 text-sm mt-1"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full border rounded px-3 py-1.5 text-sm mt-1"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Sifre</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full border rounded px-3 py-1.5 text-sm mt-1"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Sirket</label>
              <select
                value={companyId}
                onChange={e => setCompanyId(Number(e.target.value))}
                className="w-full border rounded px-3 py-1.5 text-sm mt-1"
              >
                {companies.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            {error && <p className="text-red-600 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Kaydediliyor...' : 'Kaydet'}
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
              <th className="text-left px-4 py-3 font-medium text-gray-600">Email</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Rol</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Sirket</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Durum</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {users.map(u => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-500">{u.id}</td>
                <td className="px-4 py-3 font-medium text-gray-800">{u.full_name}</td>
                <td className="px-4 py-3 text-gray-600">{u.email}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    u.role === 'admin'
                      ? 'bg-purple-100 text-purple-700'
                      : 'bg-gray-100 text-gray-600'
                  }`}>
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-600">{u.company_name}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {u.is_active ? 'Aktif' : 'Pasif'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {users.length === 0 && (
          <p className="text-center text-gray-500 py-8 text-sm">Henuz kullanici yok</p>
        )}
      </div>
    </div>
  );
}
