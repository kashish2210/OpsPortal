import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { ApiError, djangoUrl } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { ThemeToggle } from '../components/ThemeToggle';

const DEMO_LOGINS = [
  { role: 'Admin', username: 'admin', password: 'Admin@12345' },
  { role: 'Sales', username: 'sales', password: 'Sales@12345' },
  { role: 'Warehouse', username: 'warehouse', password: 'Warehouse@12345' },
  { role: 'Accounts', username: 'accounts', password: 'Accounts@12345' },
];

/**
 * SPA sign-in. Visually identical to the Django-rendered
 * `registration/login.html`, but posts to /api/auth/login/ for a JWT pair.
 */
export function LoginPage() {
  const { login, status } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = (location.state as { from?: string } | null)?.from ?? '/';

  if (status === 'authenticated') return <Navigate to={redirectTo} replace />;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Could not reach the server. Is the backend running?',
      );
    } finally {
      setSubmitting(false);
    }
  };

  const fillDemo = (demo: (typeof DEMO_LOGINS)[number]) => {
    setUsername(demo.username);
    setPassword(demo.password);
    setError(null);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
    >
      <div style={{ position: 'fixed', top: 20, right: 20 }}>
        <ThemeToggle />
      </div>

      <div className="container fade-in" style={{ maxWidth: 1000, padding: 20 }}>
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <span
            style={{
              fontSize: '2.5rem',
              fontWeight: 'bold',
              fontFamily: "'Architects Daughter', cursive",
            }}
          >
            OpsPortal
          </span>
          <p className="muted" style={{ marginTop: 4 }}>
            Mini ERP + CRM Operations Portal
          </p>
        </div>

        <div className="login-wrapper" style={{ minHeight: 'auto' }}>
          <div className="login-box card" style={{ margin: '0 auto' }}>
            <h2>OpsPortal &ndash; Login</h2>

            <form className="login-form" onSubmit={handleSubmit}>
              {error ? <div className="alert alert-error">{error}</div> : null}

              <div className="form-group">
                <label htmlFor="username">Username or e-mail</label>
                <input
                  id="username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  placeholder="you@company.com or username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  required
                  autoFocus
                />
              </div>

              <div className="form-group" style={{ position: 'relative' }}>
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
                <div style={{ textAlign: 'right', marginTop: 5 }}>
                  <a href={djangoUrl('/accounts/password/reset/')} style={{ fontSize: '0.9rem' }}>
                    Forgot password
                  </a>
                </div>
              </div>

              <div style={{ marginTop: 20 }}>
                <button
                  className="btn"
                  type="submit"
                  disabled={submitting}
                  style={{ width: '100%', backgroundColor: 'var(--accent-color)', fontWeight: 'bold' }}
                >
                  {submitting ? 'Signing in...' : 'Login'}
                </button>
              </div>

              <hr className="hr-sketch" />

              <div className="form-footer">
                <p style={{ textAlign: 'left', marginBottom: 10 }}>New here?</p>
                <div className="panel" style={{ padding: 15, marginBottom: 15, textAlign: 'left' }}>
                  <p>Sign up creates an employee account</p>
                  <p>admin assigns the role afterwards</p>
                </div>
                <a href={djangoUrl('/accounts/signup/')} className="btn" style={{ width: '100%' }}>
                  Create Account
                </a>
              </div>
            </form>
          </div>
        </div>

        <div className="card" style={{ maxWidth: 450, margin: '20px auto 0' }}>
          <h3 style={{ fontSize: '1.3rem' }}>Demo logins</h3>
          <p className="muted" style={{ marginBottom: 12 }}>
            Seeded by <span className="mono">manage.py seed_demo</span>. Click one to fill the form.
          </p>
          <div className="stack">
            {DEMO_LOGINS.map((demo) => (
              <button
                key={demo.username}
                type="button"
                className="btn btn-sm"
                onClick={() => fillDemo(demo)}
                style={{ textAlign: 'left' }}
              >
                <strong>{demo.role}</strong> &middot; <span className="mono">{demo.username}</span> /{' '}
                <span className="mono">{demo.password}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
