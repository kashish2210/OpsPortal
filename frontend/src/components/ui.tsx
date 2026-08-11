/** Small presentational building blocks shared across the pages. */

import type { ChangeEvent, ReactNode } from 'react';

import type { ChallanStatus, CustomerStatus } from '../api/types';

// ---------------------------------------------------------------------------
// Page furniture
// ---------------------------------------------------------------------------
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle ? <div className="page-subtitle">{subtitle}</div> : null}
      </div>
      {actions ? <div className="row">{actions}</div> : null}
    </div>
  );
}

export function Spinner({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="row" style={{ justifyContent: 'center', padding: '48px 0', gap: 14 }}>
      <div className="spinner" />
      <span className="muted">{label}</span>
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <p style={{ fontSize: '1.3rem', marginBottom: 8 }}>{title}</p>
      {hint ? <p>{hint}</p> : null}
      {action ? <div style={{ marginTop: 16 }}>{action}</div> : null}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="alert alert-error">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span>{message}</span>
        {onRetry ? (
          <button type="button" className="btn btn-sm" onClick={onRetry}>
            Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Badges
// ---------------------------------------------------------------------------
const CUSTOMER_STATUS_CLASS: Record<CustomerStatus, string> = {
  LEAD: 'badge-warn',
  ACTIVE: 'badge-ok',
  INACTIVE: 'badge-muted',
};

const CHALLAN_STATUS_CLASS: Record<ChallanStatus, string> = {
  DRAFT: 'badge-info',
  CONFIRMED: 'badge-ok',
  CANCELLED: 'badge-danger',
};

export function CustomerStatusBadge({ status, label }: { status: CustomerStatus; label?: string }) {
  return <span className={`badge ${CUSTOMER_STATUS_CLASS[status]}`}>{label ?? status}</span>;
}

export function ChallanStatusBadge({ status, label }: { status: ChallanStatus; label?: string }) {
  return <span className={`badge ${CHALLAN_STATUS_CLASS[status]}`}>{label ?? status}</span>;
}

export function StockBadge({ stock, minAlert }: { stock: number; minAlert: number }) {
  if (stock <= 0) return <span className="badge badge-danger">Out of stock</span>;
  if (stock <= minAlert) return <span className="badge badge-warn">Low ({stock})</span>;
  return <span className="badge badge-ok">{stock}</span>;
}

// ---------------------------------------------------------------------------
// Form controls
// ---------------------------------------------------------------------------
interface FieldProps {
  label: string;
  name: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}

export function Field({ label, name, error, hint, required, children, className }: FieldProps) {
  return (
    <div className={`form-group ${className ?? ''}`}>
      <label htmlFor={name}>
        {label}
        {required ? <span className="muted"> *</span> : null}
      </label>
      {children}
      {error ? <div className="field-error">{error}</div> : null}
      {hint && !error ? <div className="helptext">{hint}</div> : null}
    </div>
  );
}

interface TextInputProps {
  name: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'email' | 'tel' | 'number' | 'date' | 'password';
  placeholder?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  disabled?: boolean;
  min?: number;
  step?: string;
  list?: string;
  className?: string;
}

export function TextInput({
  name,
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
  error,
  hint,
  required,
  disabled,
  min,
  step,
  list,
  className,
}: TextInputProps) {
  return (
    <Field label={label} name={name} error={error} hint={hint} required={required} className={className}>
      <input
        id={name}
        name={name}
        type={type}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        min={min}
        step={step}
        list={list}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
      />
    </Field>
  );
}

export function TextArea({
  name,
  label,
  value,
  onChange,
  rows = 3,
  placeholder,
  error,
  hint,
  className,
}: {
  name: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
  error?: string;
  hint?: string;
  className?: string;
}) {
  return (
    <Field label={label} name={name} error={error} hint={hint} className={className}>
      <textarea
        id={name}
        name={name}
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  );
}

export function SelectInput({
  name,
  label,
  value,
  onChange,
  options,
  error,
  hint,
  required,
  disabled,
  placeholder,
  className,
}: {
  name: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  error?: string;
  hint?: string;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}) {
  return (
    <Field label={label} name={name} error={error} hint={hint} required={required} className={className}>
      <select
        id={name}
        name={name}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {placeholder ? <option value="">{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

// ---------------------------------------------------------------------------
// Modal & pagination
// ---------------------------------------------------------------------------
export function Modal({
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal-card" style={wide ? { maxWidth: 900 } : undefined}>
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ marginBottom: 0 }}>{title}</h3>
          <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>
        {children}
        {footer ? (
          <div className="row row-end" style={{ marginTop: 20 }}>
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function Pagination({
  page,
  totalPages,
  count,
  onChange,
}: {
  page: number;
  totalPages: number;
  count: number;
  onChange: (page: number) => void;
}) {
  if (count === 0) return null;
  return (
    <div className="pagination">
      <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        &larr; Previous
      </button>
      <span className="muted">
        Page {page} of {totalPages} &middot; {count} record{count === 1 ? '' : 's'}
      </span>
      <button
        type="button"
        className="btn btn-sm"
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
      >
        Next &rarr;
      </button>
    </div>
  );
}

export function StatTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: 'ok' | 'warn' | 'danger';
}) {
  const color =
    tone === 'danger' ? 'var(--danger-color)' : tone === 'warn' ? 'var(--warn-color)' : undefined;
  return (
    <div className="overview-card">
      <div className="overview-label">{label}</div>
      <div className="overview-value" style={color ? { color } : undefined}>
        {value}
      </div>
      {hint ? <div className="muted" style={{ fontSize: '0.95rem', marginTop: 6 }}>{hint}</div> : null}
    </div>
  );
}
