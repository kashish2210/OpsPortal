import { useEffect, useState, type FormEvent } from 'react';

import { ApiError, djangoUrl } from '../api/client';
import { auth } from '../api/endpoints';
import { useAuth } from '../auth/AuthContext';
import { ROLE_BADGE } from '../auth/permissions';
import { useToast } from '../components/Toast';
import { PageHeader, TextInput } from '../components/ui';
import { dateTime } from '../utils/format';

export function ProfilePage() {
  const { user, setUser } = useAuth();
  const toast = useToast();

  const [details, setDetails] = useState({ first_name: '', last_name: '', phone: '', department: '' });
  const [detailErrors, setDetailErrors] = useState<Record<string, string>>({});
  const [savingDetails, setSavingDetails] = useState(false);

  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    if (!user) return;
    setDetails({
      first_name: user.first_name,
      last_name: user.last_name,
      phone: user.phone,
      department: user.department,
    });
  }, [user]);

  if (!user) return null;

  const saveDetails = async (event: FormEvent) => {
    event.preventDefault();
    setSavingDetails(true);
    setDetailErrors({});
    try {
      const updated = await auth.updateMe(details);
      setUser(updated);
      toast.success('Profile updated.');
    } catch (error) {
      if (error instanceof ApiError) {
        setDetailErrors(error.fieldErrors());
        toast.error(error.message);
      } else {
        toast.error('Could not reach the server.');
      }
    } finally {
      setSavingDetails(false);
    }
  };

  const savePassword = async (event: FormEvent) => {
    event.preventDefault();
    setPasswordError(null);

    if (newPassword !== confirmPassword) {
      setPasswordError('The two new passwords do not match.');
      return;
    }

    setSavingPassword(true);
    try {
      await auth.changePassword(oldPassword, newPassword);
      toast.success('Password changed.');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      if (error instanceof ApiError) {
        const fields = error.fieldErrors();
        setPasswordError(fields.new_password ?? fields.old_password ?? error.message);
      } else {
        setPasswordError('Could not reach the server.');
      }
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div className="fade-in">
      <PageHeader
        title="My profile"
        subtitle={
          <span className="row" style={{ gap: 8 }}>
            <span className="mono">{user.username}</span>
            <span className={`badge ${ROLE_BADGE[user.role]}`}>{user.role_display}</span>
            {user.is_email_verified ? (
              <span className="badge badge-ok">E-mail verified</span>
            ) : (
              <span className="badge badge-warn">E-mail unverified</span>
            )}
          </span>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        <section className="card">
          <h3>Account</h3>
          <div className="row" style={{ gap: 14, marginBottom: 16 }}>
            {user.avatar_url ? (
              <img src={user.avatar_url} alt="" className="avatar" style={{ width: 64, height: 64 }} />
            ) : (
              <span className="avatar" style={{ width: 64, height: 64, fontSize: '1.4rem' }}>
                {user.initials}
              </span>
            )}
            <div>
              <strong style={{ fontSize: '1.2rem' }}>{user.full_name || user.username}</strong>
              <div className="muted">{user.email}</div>
            </div>
          </div>

          <table className="credential-table">
            <tbody>
              <tr>
                <td className="muted">Last login</td>
                <td>{dateTime(user.last_login)}</td>
              </tr>
              <tr>
                <td className="muted">Joined</td>
                <td>{dateTime(user.date_joined)}</td>
              </tr>
            </tbody>
          </table>

          <hr className="hr-sketch" />
          <p className="muted" style={{ marginBottom: 12 }}>
            Your e-mail address, avatar and account settings live on the Django account pages.
          </p>
          <div className="row">
            <a href={djangoUrl('/accounts/profile/')} className="btn btn-sm">
              Account settings
            </a>
            <a href={djangoUrl('/accounts/email/')} className="btn btn-sm">
              E-mail address
            </a>
          </div>
        </section>

        <section className="card">
          <h3>Personal details</h3>
          <form onSubmit={saveDetails}>
            <div className="form-grid">
              <TextInput
                name="first_name"
                label="First name"
                value={details.first_name}
                onChange={(value) => setDetails((c) => ({ ...c, first_name: value }))}
                error={detailErrors.first_name}
              />
              <TextInput
                name="last_name"
                label="Last name"
                value={details.last_name}
                onChange={(value) => setDetails((c) => ({ ...c, last_name: value }))}
                error={detailErrors.last_name}
              />
              <TextInput
                name="phone"
                label="Phone"
                type="tel"
                value={details.phone}
                onChange={(value) => setDetails((c) => ({ ...c, phone: value }))}
                error={detailErrors.phone}
              />
              <TextInput
                name="department"
                label="Department"
                value={details.department}
                onChange={(value) => setDetails((c) => ({ ...c, department: value }))}
                error={detailErrors.department}
              />
            </div>
            <p className="helptext" style={{ marginBottom: 14 }}>
              Your role is set by an administrator and cannot be changed here.
            </p>
            <button type="submit" className="btn btn-accent" disabled={savingDetails}>
              {savingDetails ? 'Saving...' : 'Save details'}
            </button>
          </form>
        </section>

        <section className="card">
          <h3>Change password</h3>
          <form onSubmit={savePassword}>
            {passwordError ? <div className="alert alert-error">{passwordError}</div> : null}
            <TextInput
              name="old_password"
              label="Current password"
              type="password"
              value={oldPassword}
              onChange={setOldPassword}
              required
            />
            <TextInput
              name="new_password"
              label="New password"
              type="password"
              value={newPassword}
              onChange={setNewPassword}
              required
              hint="At least 8 characters, not entirely numeric, not a common password."
            />
            <TextInput
              name="confirm_password"
              label="Confirm new password"
              type="password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              required
            />
            <button type="submit" className="btn btn-accent" disabled={savingPassword}>
              {savingPassword ? 'Saving...' : 'Change password'}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
