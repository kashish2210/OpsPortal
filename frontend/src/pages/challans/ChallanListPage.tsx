import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { challans } from '../../api/endpoints';
import { IfAllowed } from '../../auth/guards';
import {
  ChallanStatusBadge,
  EmptyState,
  ErrorNote,
  PageHeader,
  Pagination,
  Spinner,
} from '../../components/ui';
import { usePaginatedResource } from '../../hooks/useApiResource';
import { useDebounce } from '../../hooks/useDebounce';
import { date, money } from '../../utils/format';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'DRAFT', label: 'Draft' },
  { value: 'CONFIRMED', label: 'Confirmed' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

export function ChallanListPage() {
  const [params, setParams] = useSearchParams();

  const [search, setSearch] = useState(params.get('q') ?? '');
  const debouncedSearch = useDebounce(search);

  const status = params.get('status') ?? '';
  const customer = params.get('customer') ?? '';
  const dateFrom = params.get('date_from') ?? '';
  const dateTo = params.get('date_to') ?? '';
  const ordering = params.get('ordering') ?? '-challan_date';
  const page = Number(params.get('page') ?? 1);

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
      challans.list(
        {
          q: debouncedSearch || undefined,
          status: status || undefined,
          customer: customer || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          ordering,
          page,
        },
        signal,
      ),
    [debouncedSearch, status, customer, dateFrom, dateTo, ordering, page],
  );

  return (
    <div className="fade-in">
      <PageHeader
        title="Sales challans"
        subtitle="Confirming a challan deducts stock; cancelling a confirmed one puts it back."
        actions={
          <IfAllowed capability="challans.write">
            <Link to="/challans/new" className="btn btn-accent">
              + New challan
            </Link>
          </IfAllowed>
        }
      />

      <div className="toolbar">
        <input
          className="grow"
          type="search"
          placeholder="Search challan number, customer, vehicle or SKU..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search challans"
        />
        <select value={status} onChange={(event) => setFilter('status', event.target.value)} aria-label="Status">
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={dateFrom}
          onChange={(event) => setFilter('date_from', event.target.value)}
          aria-label="From date"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(event) => setFilter('date_to', event.target.value)}
          aria-label="To date"
        />
        <select value={ordering} onChange={(event) => setFilter('ordering', event.target.value)} aria-label="Sort">
          <option value="-challan_date">Newest first</option>
          <option value="challan_date">Oldest first</option>
          <option value="-grand_total">Highest value</option>
          <option value="grand_total">Lowest value</option>
        </select>
        {customer ? (
          <button type="button" className="btn btn-sm" onClick={() => setFilter('customer', '')}>
            Clear customer filter
          </button>
        ) : null}
      </div>

      {error ? <ErrorNote message={error} onRetry={reload} /> : null}
      {loading && items.length === 0 ? <Spinner /> : null}

      {!loading && items.length === 0 && !error ? (
        <EmptyState
          title="No challans match this view"
          hint="Try clearing the filters."
          action={
            <IfAllowed capability="challans.write">
              <Link to="/challans/new" className="btn btn-accent">
                Raise the first challan
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
                <th>Challan no.</th>
                <th>Date</th>
                <th>Customer</th>
                <th>Status</th>
                <th className="num">Lines</th>
                <th className="num">Qty</th>
                <th className="num">Total</th>
                <th>Raised by</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((challan) => (
                <tr key={challan.id}>
                  <td className="mono nowrap">
                    <Link to={`/challans/${challan.id}`}>{challan.challan_number}</Link>
                  </td>
                  <td className="nowrap">{date(challan.challan_date)}</td>
                  <td>
                    <Link to={`/customers/${challan.customer}`}>{challan.customer_name}</Link>
                    {challan.customer_business_name ? (
                      <div className="muted" style={{ fontSize: '0.95rem' }}>
                        {challan.customer_business_name}
                      </div>
                    ) : null}
                  </td>
                  <td>
                    <ChallanStatusBadge status={challan.status} label={challan.status_display} />
                  </td>
                  <td className="num">{challan.item_count}</td>
                  <td className="num">{challan.total_quantity}</td>
                  <td className="num nowrap">{money(challan.grand_total)}</td>
                  <td className="nowrap">{challan.created_by_name ?? '-'}</td>
                  <td className="nowrap">
                    <Link to={`/challans/${challan.id}`} className="btn btn-sm">
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
