import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/client';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await login(email, password);
      localStorage.setItem('token', response.data.access_token);
      localStorage.setItem('user', JSON.stringify(response.data.user));
      navigate('/');
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900">
      <div className="bg-gray-800 p-8 rounded-lg shadow-lg w-96 border border-gray-700">
        <h1 className="text-2xl font-bold mb-2 text-center text-white">
          Tedarikci Raporlama Platformu
        </h1>
        <p className="text-sm text-gray-400 mb-6 text-center">Performans Analiz Sistemi</p>

        {error && (
          <div className="bg-red-900/50 text-red-300 p-3 rounded mb-4 text-sm border border-red-800">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <label className="block text-sm font-medium mb-1 text-gray-300">Email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 mb-4 focus:outline-none focus:border-blue-500"
            placeholder="admin@superstore.com"
            required
          />

          <label className="block text-sm font-medium mb-1 text-gray-300">Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 mb-6 focus:outline-none focus:border-blue-500"
            placeholder="••••••••"
            required
          />

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p className="text-xs text-gray-500 mt-6 text-center">v0.7.0</p>
      </div>
    </div>
  );
}
