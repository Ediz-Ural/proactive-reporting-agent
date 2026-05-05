import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Pipeline from './pages/Pipeline';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import Login from './pages/Login';
import UploadData from './pages/admin/UploadData';
import Companies from './pages/admin/Companies';
import Users from './pages/admin/Users';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('token');
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  if (user.role !== 'admin') {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pipeline" element={<AdminRoute><Pipeline /></AdminRoute>} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<AdminRoute><Settings /></AdminRoute>} />
          <Route path="/admin/upload" element={<AdminRoute><UploadData /></AdminRoute>} />
          <Route path="/admin/companies" element={<AdminRoute><Companies /></AdminRoute>} />
          <Route path="/admin/users" element={<AdminRoute><Users /></AdminRoute>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
