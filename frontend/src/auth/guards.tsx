import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { Spinner } from '../components/ui';
import { useAuth } from './AuthContext';
import type { Capability } from './permissions';

/** Blocks a route until a user is loaded; bounces anonymous visitors to /login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') return <Spinner label="Checking your session..." />;
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <>{children}</>;
}

/** Route-level role gate. The server enforces the same rule. */
export function RequireCapability({
  capability,
  children,
}: {
  capability: Capability;
  children: ReactNode;
}) {
  const { can, user } = useAuth();

  if (!can(capability)) {
    return (
      <div className="card">
        <h2>Not available for your role</h2>
        <p className="muted">
          Your account is on the <strong>{user?.role_display}</strong> role, which does not have access to
          this screen. Ask an administrator if you need it.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}

/** Renders children only when the capability is held (for buttons and links). */
export function IfAllowed({ capability, children }: { capability: Capability; children: ReactNode }) {
  const { can } = useAuth();
  return can(capability) ? <>{children}</> : null;
}
