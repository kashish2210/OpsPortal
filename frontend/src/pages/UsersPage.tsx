import { useState, type FormEvent } from 'react';

import { ApiError } from '../api/client';
import { users } from '../api/endpoints';
import type { User } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { ROLE_BADGE } from '../auth/permissions';
import { useToast } from '../components/Toast';
import {
  EmptyState,
  ErrorNote,
  Modal,
  PageHeader,
  Pagination,
  SelectInput,
  Spinner,
  TextInput,
} from '../components/ui';
import { usePaginatedResource } from '../hooks/useApiResource';
import { dateTime } from '../utils/format';

const ROLE_OPTIONS = [
  { value: 'ADMIN', label: 'Admin' },
  { value: 'SALES', label: 'Sales' },
  { value: 'WAREHOUSE', label: 'Warehouse' },
  { value: 'ACCOUNTS', label: 'Accounts' },
];

const EMPTY_FORM = {
  username: '',
  email: '',
  first_name: '',
  last_name: '',
  role: 'SALES',
  phone: '',
  department: '',
  password: '',
};

export function UsersPage() {
  const { user: currentUser } = useAuth();
  const toast = useToast();

  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState('');
  const [search, setSearch] = useState('');

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [modalError, setModalError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  const { items, count, totalPages, loading, error, reload } = usePaginatedResource(
    (signal) => users.list({ role: roleFilter || undefined, q: search || undefined, page }, signal),
    [roleFilter, search, page],
  );

  const update = (key: keyof typeof EMPTY_FORM, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const createUser = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setModalError(null);
    setFieldErrors({});
    try {
      const created = await users.create(form);
      toast.success(`${created.username} created on the ${created.role_display} role.`);
      setShowCreate(false);
      setForm(EMPTY_FORM);
      reload();
    } catch (err) {
      if (err instanceof ApiError) {
        setFieldErrors(err.fieldErrors());
        setModalError(err.message);
      } else {
        setModalError('Could not reach the server.');
      }
    } finally {
      setSaving(false);
    }
  };

  const changeRole = async (target: User, role: string) => {
    setBusyId(target.id);
    try {
      await users.update(target.id, { role });
      toast.success(`${target.username} moved to ${role}.`);
      reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not change the role.');
    } finally {
      setBusyId(null);
    }
  };

  const toggleActive = async (target: User) => {
    setBusyId(target.id);
    try {
      if (target.is_active) await users.deactivate(target.id);
      else await users.activate(target.id);
      toast.success(`${target.username} ${target.is_active ? 'deactivated' : 'reactivated'}.`);
      reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not update the account.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="fade-in">
      <PageHeader
        title="Users & roles"
        subtitle="Admin only. Roles decide which modules each employee can read and edit."
        actions={
          <button type="button" className="btn btn-accent" onClick={() => setShowCreate(true)}>
            + Add user
          </button>
        }
      />

      <div className="panel">
        <strong>Role matrix</strong>
        <ul style={{ marginTop: 10, paddingLeft: 20 }}>
          <li>
            <strong>Admin</strong> - everything, including user management.
          </li>
          <li>
            <strong>Sales</strong> - customers and challans (write); products and stock (read).
          </li>
          <li>
            <strong>Warehouse</strong> - products and stock (write); customers and challans (read).
          </li>
          <li>
            <strong>Accounts</strong> - read-only across every module.
          </li>
        </ul>
      </div>

      <div className="toolbar">
        <input
          className="grow"
          type="search"
          placeholder="Search username, name or e-mail..."
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          aria-label="Search users"
        />
        <select
          value={roleFilter}
          onChange={(event) => {
            setRoleFilter(event.target.value);
            setPage(1);
          }}
          aria-label="Role"
        >
          <option value="">All roles</option>
          {ROLE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {error ? <ErrorNote message={error} onRetry={reload} /> : null}
      {loading && items.length === 0 ? <Spinner /> : null}
      {!loading && items.length === 0 && !error ? <EmptyState title="No users match this view" /> : null}

      {items.length > 0 ? (
        <div className="table-wrap">
          <table className="sketch-table">
            <thead>
              <tr>
                <th>User</th>
                <th>E-mail</th>
                <th>Role</th>
                <th>Department</th>
                <th>Status</th>
                <th>Last login</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} style={row.is_active ? undefined : { opacity: 0.6 }}>
                  <td>
                    <strong>{row.full_name || row.username}</strong>
                    <div className="muted mono" style={{ fontSize: '0.95rem' }}>
                      {row.username}
                    </div>
                  </td>
                  <td>{row.email}</td>
                  <td>
                    <select
                      value={row.role}
                      disabled={busyId === row.id || row.id === currentUser?.id}
                      onChange={(event) => changeRole(row, event.target.value)}
                      style={{ padding: '6px 10px', fontSize: '1rem' }}
                      aria-label={`Role for ${row.username}`}
                    >
                      {ROLE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <div style={{ marginTop: 6 }}>
                      <span className={`badge ${ROLE_BADGE[row.role]}`}>{row.role_display}</span>
                    </div>
                  </td>
                  <td>{row.department || '-'}</td>
                  <td>
                    <span className={`badge ${row.is_active ? 'badge-ok' : 'badge-muted'}`}>
                      {row.is_active ? 'Active' : 'Deactivated'}
                    </span>
                  </td>
                  <td className="nowrap">{dateTime(row.last_login)}</td>
                  <td className="nowrap">
                    <button
                      type="button"
                      className={`btn btn-sm ${row.is_active ? 'btn-danger' : ''}`}
                      disabled={busyId === row.id || row.id === currentUser?.id}
                      onClick={() => toggleActive(row)}
                      title={row.id === currentUser?.id ? 'You cannot deactivate yourself' : undefined}
                    >
                      {row.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <Pagination page={page} totalPages={totalPages} count={count} onChange={setPage} />

      {showCreate ? (
        <Modal
          title="Add a user"
          onClose={() => setShowCreate(false)}
          wide
          footer={
            <>
              <button type="button" className="btn" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button type="submit" form="user-form" className="btn btn-accent" disabled={saving}>
                {saving ? 'Creating...' : 'Create user'}
              </button>
            </>
          }
        >
          <form id="user-form" onSubmit={createUser}>
            {modalError ? <div className="alert alert-error">{modalError}</div> : null}
            <div className="form-grid">
              <TextInput
                name="username"
                label="Username"
                value={form.username}
                onChange={(value) => update('username', value)}
                error={fieldErrors.username}
                required
              />
              <TextInput
                name="email"
                label="E-mail"
                type="email"
                value={form.email}
                onChange={(value) => update('email', value)}
                error={fieldErrors.email}
                required
              />
              <TextInput
                name="first_name"
                label="First name"
                value={form.first_name}
                onChange={(value) => update('first_name', value)}
                error={fieldErrors.first_name}
              />
              <TextInput
                name="last_name"
                label="Last name"
                value={form.last_name}
                onChange={(value) => update('last_name', value)}
                error={fieldErrors.last_name}
              />
              <SelectInput
                name="role"
                label="Role"
                value={form.role}
                onChange={(value) => update('role', value)}
                options={ROLE_OPTIONS}
                error={fieldErrors.role}
                required
              />
              <TextInput
                name="department"
                label="Department"
                value={form.department}
                onChange={(value) => update('department', value)}
                error={fieldErrors.department}
              />
              <TextInput
                name="phone"
                label="Phone"
                type="tel"
                value={form.phone}
                onChange={(value) => update('phone', value)}
                error={fieldErrors.phone}
              />
              <TextInput
                name="password"
                label="Initial password"
                type="password"
                value={form.password}
                onChange={(value) => update('password', value)}
                error={fieldErrors.password}
                required
                hint="At least 8 characters. The user can change it from their profile."
              />
            </div>
          </form>
        </Modal>
      ) : null}
    </div>
  );
}
