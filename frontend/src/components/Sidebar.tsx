import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Play,
  FileText,
  BarChart3,
  Settings,
} from 'lucide-react';

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/pipeline', label: 'Pipeline', icon: Play },
  { to: '/reports', label: 'Raporlar', icon: FileText },
  { to: '/analytics', label: 'Analizler', icon: BarChart3 },
  { to: '/settings', label: 'Ayarlar', icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col shrink-0">
      <div className="px-4 py-5 border-b border-gray-800">
        <h1 className="text-base font-semibold text-white tracking-tight">
          Proaktif Raporlama
        </h1>
        <p className="text-xs text-gray-500 mt-0.5">Multi-Agent System</p>
      </div>
      <nav className="flex-1 py-3 space-y-0.5 px-2">
        {links.map(({ to, label, icon: Icon }) => (
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
      </nav>
      <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
        v0.6.0
      </div>
    </aside>
  );
}
