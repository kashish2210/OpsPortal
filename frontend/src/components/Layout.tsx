import { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';

import { djangoUrl } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { ROLE_BADGE, type Capability } from '../auth/permissions';
import { ThemeToggle } from './ThemeToggle';
import { useToast } from './Toast';

interface NavItem {
  to: string;
  label: string;
  capability?: Capability;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/customers', label: 'Customers' },
  { to: '/products', label: 'Products' },
  { to: '/stock', label: 'Stock log' },
  { to: '/challans', label: 'Sales challans' },
  { to: '/users', label: 'Users', capability: 'users.manage' },
];

export function Layout() {
  const { user, logout, can } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  const handleLogout = async () => {
    setSigningOut(true);
    try {
      await logout();
      toast.info('Signed out.');
      navigate('/login', { replace: true });
    } finally {
      setSigningOut(false);
    }
  };

  const visibleItems = NAV_ITEMS.filter((item) => !item.capability || can(item.capability));

  return (
    <div className="container">
      <header className="navbar">
        <div className="navbar-brand">
          <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
            OpsPortal
          </Link>
        </div>

        <div className="navbar-links">
          {user ? (
            <div className="row" style={{ gap: 12 }}>
              <Link to="/profile" className="row" style={{ gap: 8, textDecoration: 'none' }}>
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt="" className="avatar" />
                ) : (
                  <span className="avatar">{user.initials}</span>
                )}
              </Link>
              <span className={`badge ${ROLE_BADGE[user.role]} nowrap`}>{user.role_display}</span>
              <button type="button" className="btn btn-sm" onClick={handleLogout} disabled={signingOut}>
                {signingOut ? 'Signing out...' : 'Logout'}
              </button>
            </div>
          ) : (
            <a href={djangoUrl('/accounts/login/')} className="btn btn-sm">
              Login
            </a>
          )}
          <ThemeToggle />
        </div>
      </header>

      <div className="app-layout">
        <aside className="sidebar">
          <ul>
            {visibleItems.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} end={item.end} className={({ isActive }) => (isActive ? 'active' : '')}>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>

          <hr className="hr-sketch" />

          <ul>
            <li>
              <a href={djangoUrl('/accounts/profile/')}>Account settings</a>
            </li>
            <li>
              <a href={djangoUrl('/api/docs/')} target="_blank" rel="noreferrer">
                API docs
              </a>
            </li>
            {user?.is_staff ? (
              <li>
                <a href={djangoUrl('/admin/')} target="_blank" rel="noreferrer">
                  Django admin
                </a>
              </li>
            ) : null}
          </ul>
        </aside>

        <main className="main-content">
          <Outlet />
        </main>
      </div>

      <footer className="footer">
        <p className="muted">
          OpsPortal &middot; Mini ERP + CRM operations portal
          {user ? ` · signed in as ${user.full_name || user.username}` : ''}
        </p>
      </footer>
    </div>
  );
}
