import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Play,
  FileText,
  Settings,
  Upload,
  Building2,
  Users,
  LogOut,
} from 'lucide-react';

const userLinks = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
];

const adminLinks = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/pipeline', label: 'Rapor Olustur', icon: Play },
  { to: '/reports', label: 'Raporlar', icon: FileText },
  { to: '/settings', label: 'Ayarlar', icon: Settings },
  { to: '/admin/upload', label: 'Veri Yukle', icon: Upload },
  { to: '/admin/companies', label: 'Tedarikciler', icon: Building2 },
  { to: '/admin/users', label: 'Kullanicilar', icon: Users },
];

export default function Sidebar() {
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const isAdmin = user.role === 'admin';
  const links = isAdmin ? adminLinks : userLinks;

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  };

  const mainLinks = isAdmin ? links.filter(l => !['/admin/upload', '/admin/companies', '/admin/users'].includes(l.to)) : links;
  const adminOnlyLinks = isAdmin ? links.filter(l => ['/admin/upload', '/admin/companies', '/admin/users'].includes(l.to)) : [];

  return (
    <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col shrink-0">
      <div className="px-4 py-5 border-b border-gray-800">
        <h1 className="text-base font-semibold text-white tracking-tight">
          Tedarikci Raporlama
        </h1>
        <p className="text-xs text-gray-500 mt-0.5">Performans Platformu</p>
      </div>
      <nav className="flex-1 py-3 space-y-0.5 px-2">
        {mainLinks.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}

        {adminOnlyLinks.length > 0 && (
          <>
            <div className="pt-3 pb-1 px-3">
              <p className="text-xs text-gray-500 uppercase tracking-wider">Admin</p>
            </div>
            {adminOnlyLinks.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'hover:bg-gray-800 hover:text-white'
                  }`
                }
              >
                <Icon size={18} />
                {label}
              </NavLink>
            ))}
          </>
        )}
      </nav>

      <div className="px-4 py-3 border-t border-gray-800">
        <p className="text-sm text-gray-300 truncate">{user.full_name || 'User'}</p>
        <p className="text-xs text-gray-500 truncate">{user.company_name || ''}</p>
        <p className="text-xs text-gray-600 mb-2">{user.role || ''}</p>
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300 transition-colors"
        >
          <LogOut size={14} />
          Logout
        </button>
      </div>
      <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-600">
        v0.7.0
      </div>
    </aside>
  );
}
