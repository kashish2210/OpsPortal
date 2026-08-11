import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { djangoUrl, exchangeSessionForTokens } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Spinner } from '../components/ui';

/**
 * Landing spot for the "Open OpsPortal" button on the Django profile page.
 *
 * Trades the Django session cookie for a JWT pair via
 * `POST /api/auth/session-token/`, then drops the user on the dashboard. This
 * is what lets the server-rendered auth pages and the SPA share one login.
 */
export function HandoffPage() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;

    (async () => {
      try {
        await exchangeSessionForTokens();
        if (!active) return;
        await refreshUser();
        navigate('/', { replace: true });
      } catch {
        if (active) setFailed(true);
      }
    })();

    return () => {
      active = false;
    };
  }, [navigate, refreshUser]);

  if (failed) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 20 }}>
        <div className="login-box card">
          <h2>Session handoff failed</h2>
          <div className="alert alert-warning">
            We could not find an active Django session for this browser.
          </div>
          <p className="muted">
            Sign in again, either on the Django page or with the in-app form.
          </p>
          <hr className="hr-sketch" />
          <div className="stack">
            <a href={djangoUrl('/accounts/login/')} className="btn btn-block">
              Django login page
            </a>
            <Link to="/login" className="btn btn-block btn-accent">
              In-app login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
      <Spinner label="Handing your session over to the app..." />
    </div>
  );
}
