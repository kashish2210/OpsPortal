import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 20 }}>
      <div className="login-box card" style={{ textAlign: 'center' }}>
        <h2>Page not found</h2>
        <p className="muted">That screen does not exist in OpsPortal.</p>
        <hr className="hr-sketch" />
        <Link to="/" className="btn btn-accent btn-block">
          Back to the dashboard
        </Link>
      </div>
    </div>
  );
}
