/** Display helpers - Indian locale, since this is a wholesale/distribution ERP. */

const currency = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
});

const compactNumber = new Intl.NumberFormat('en-IN');

export function money(value: string | number | null | undefined): string {
  const amount = typeof value === 'string' ? Number.parseFloat(value) : value;
  if (amount === null || amount === undefined || Number.isNaN(amount)) return '-';
  return currency.format(amount);
}

export function quantity(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return compactNumber.format(value);
}

export function date(value: string | null | undefined): string {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '-';
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '-';
  return parsed.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** "3 days ago" / "in 2 days" - used for follow-up dates. */
export function relativeDays(value: string | null | undefined): string {
  if (!value) return '-';
  const target = new Date(value);
  if (Number.isNaN(target.getTime())) return '-';

  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(target) - startOfDay(new Date())) / 86_400_000);

  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days === -1) return 'yesterday';
  return days > 0 ? `in ${days} days` : `${Math.abs(days)} days ago`;
}

/** Today in YYYY-MM-DD, for date inputs. */
export function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
