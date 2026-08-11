import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { customers } from '../../api/endpoints';
import { IfAllowed } from '../../auth/guards';
import {
  CustomerStatusBadge,
  EmptyState,
  ErrorNote,
  PageHeader,
  Pagination,
  Spinner,
} from '../../components/ui';
import { useDebounce } from '../../hooks/useDebounce';
import { usePaginatedResource } from '../../hooks/useApiResource';
import { date, relativeDays } from '../../utils/format';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'LEAD', label: 'Lead' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'INACTIVE', label: 'Inactive' },
];

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'RETAIL', label: 'Retail' },
  { value: 'WHOLESALE', label: 'Wholesale' },
  { value: 'DISTRIBUTOR', label: 'Distributor' },
];

const FOLLOW_UP_OPTIONS = [
  { value: '', label: 'Any follow-up' },
  { value: 'due', label: 'Due or overdue' },
  { value: 'upcoming', label: 'Upcoming' },
  { value: 'none', label: 'Not scheduled' },
];

export function CustomerListPage() {
  const [params, setParams] = useSearchParams();

  const [search, setSearch] = useState(params.get('q') ?? '');
  const debouncedSearch = useDebounce(search);

  const status = params.get('status') ?? '';
  const customerType = params.get('customer_type') ?? '';
  const followUp = params.get('follow_up') ?? '';
  const ordering = params.get('ordering') ?? '-created_at';
  const page = Number(params.get('page') ?? 1);

  // Push the debounced search term into the URL so the list is shareable.
  useEffect(() => {
    const current = params.get('q') ?? '';
    if (current === debouncedSearch) return;
    const next = new URLSearchParams(params);
    if (debouncedSearch) next.set('q', debouncedSearch);
    else next.delete('q');
    next.delete('page');
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setParams(next);
  };

  const { items, count, totalPages, loading, error, reload } = usePaginatedResource(
    (signal) =>
      customers.list(
        {
          q: debouncedSearch || undefined,
          status: status || undefined,
          customer_type: customerType || undefined,
          follow_up: followUp || undefined,
          ordering,
          page,
        },
        signal,
      ),
    [debouncedSearch, status, customerType, followUp, ordering, page],
  );

  return (
    <div className="fade-in">
      <PageHeader
        title="Customers"
        subtitle="Retailers, wholesalers and distributors, with their CRM follow-ups."
        actions={
          <IfAllowed capability="customers.write">
            <Link to="/customers/new" className="btn btn-accent">
              + Add customer
            </Link>
          </IfAllowed>
        }
      />

      <div className="toolbar">
        <input
          className="grow"
          type="search"
          placeholder="Search name, business, mobile, e-mail, code, GST or city..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search customers"
        />
        <select value={status} onChange={(event) => setFilter('status', event.target.value)} aria-label="Status">
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={customerType}
          onChange={(event) => setFilter('customer_type', event.target.value)}
          aria-label="Customer type"
        >
          {TYPE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={followUp}
          onChange={(event) => setFilter('follow_up', event.target.value)}
          aria-label="Follow-up"
        >
          {FOLLOW_UP_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select value={ordering} onChange={(event) => setFilter('ordering', event.target.value)} aria-label="Sort">
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="name">Name A-Z</option>
          <option value="-name">Name Z-A</option>
          <option value="follow_up_date">Follow-up date</option>
        </select>
      </div>

      {error ? <ErrorNote message={error} onRetry={reload} /> : null}
      {loading && items.length === 0 ? <Spinner /> : null}

      {!loading && items.length === 0 && !error ? (
        <EmptyState
          title="No customers match this view"
          hint="Try clearing the filters or searching for something else."
          action={
            <IfAllowed capability="customers.write">
              <Link to="/customers/new" className="btn btn-accent">
                Add the first customer
              </Link>
            </IfAllowed>
          }
        />
      ) : null}

      {items.length > 0 ? (
        <div className="table-wrap">
          <table className="sketch-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Customer</th>
                <th>Mobile</th>
                <th>Type</th>
                <th>Status</th>
                <th>City</th>
                <th>Next follow-up</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((customer) => (
                <tr key={customer.id}>
                  <td className="mono nowrap">{customer.code}</td>
                  <td>
                    <Link to={`/customers/${customer.id}`}>
                      <strong>{customer.name}</strong>
                    </Link>
                    {customer.business_name ? (
                      <div className="muted" style={{ fontSize: '0.95rem' }}>
                        {customer.business_name}
                      </div>
                    ) : null}
                  </td>
                  <td className="mono nowrap">{customer.mobile}</td>
                  <td className="nowrap">{customer.customer_type_display}</td>
                  <td>
                    <CustomerStatusBadge status={customer.status} label={customer.status_display} />
                  </td>
                  <td>{customer.city || '-'}</td>
                  <td className="nowrap">
                    {customer.follow_up_date ? (
                      <>
                        {date(customer.follow_up_date)}
                        <div
                          className={customer.is_follow_up_due ? '' : 'muted'}
                          style={{
                            fontSize: '0.95rem',
                            color: customer.is_follow_up_due ? 'var(--danger-color)' : undefined,
                          }}
                        >
                          {relativeDays(customer.follow_up_date)}
                        </div>
                      </>
                    ) : (
                      <span className="muted">Not scheduled</span>
                    )}
                  </td>
                  <td className="nowrap">
                    <Link to={`/customers/${customer.id}`} className="btn btn-sm">
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <Pagination
        page={page}
        totalPages={totalPages}
        count={count}
        onChange={(next) => setFilter('page', String(next))}
      />
    </div>
  );
}
