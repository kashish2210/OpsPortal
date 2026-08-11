import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { stock } from '../api/endpoints';
import { EmptyState, ErrorNote, PageHeader, Pagination, Spinner } from '../components/ui';
import { usePaginatedResource } from '../hooks/useApiResource';
import { useDebounce } from '../hooks/useDebounce';
import { dateTime } from '../utils/format';

const REASONS = [
  { value: '', label: 'All reasons' },
  { value: 'OPENING', label: 'Opening balance' },
  { value: 'PURCHASE', label: 'Purchase received' },
  { value: 'SALE', label: 'Sales challan' },
  { value: 'SALES_RETURN', label: 'Sales return' },
  { value: 'PURCHASE_RETURN', label: 'Purchase return' },
  { value: 'CHALLAN_CANCELLED', label: 'Challan cancelled' },
  { value: 'DAMAGE', label: 'Damaged / expired' },
  { value: 'ADJUSTMENT', label: 'Manual adjustment' },
  { value: 'TRANSFER', label: 'Warehouse transfer' },
];

export function StockMovementsPage() {
  const [params, setParams] = useSearchParams();

  const [search, setSearch] = useState(params.get('search') ?? '');
  const debouncedSearch = useDebounce(search);

  const movementType = params.get('movement_type') ?? '';
  const reason = params.get('reason') ?? '';
  const createdAfter = params.get('created_after') ?? '';
  const createdBefore = params.get('created_before') ?? '';
  const page = Number(params.get('page') ?? 1);

  useEffect(() => {
    const current = params.get('search') ?? '';
    if (current === debouncedSearch) return;
    const next = new URLSearchParams(params);
    if (debouncedSearch) next.set('search', debouncedSearch);
    else next.delete('search');
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
      stock.list(
        {
          search: debouncedSearch || undefined,
          movement_type: movementType || undefined,
          reason: reason || undefined,
          created_after: createdAfter || undefined,
          created_before: createdBefore || undefined,
          page,
        },
        signal,
      ),
    [debouncedSearch, movementType, reason, createdAfter, createdBefore, page],
  );

  return (
    <div className="fade-in">
      <PageHeader
        title="Stock movement log"
        subtitle="Append-only ledger of every change to stock, across all products."
      />

      <div className="toolbar">
        <input
          className="grow"
          type="search"
          placeholder="Search product, SKU, reference or notes..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search movements"
        />
        <select
          value={movementType}
          onChange={(event) => setFilter('movement_type', event.target.value)}
          aria-label="Direction"
        >
          <option value="">IN and OUT</option>
          <option value="IN">Stock in only</option>
          <option value="OUT">Stock out only</option>
        </select>
        <select value={reason} onChange={(event) => setFilter('reason', event.target.value)} aria-label="Reason">
          {REASONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={createdAfter}
          onChange={(event) => setFilter('created_after', event.target.value)}
          aria-label="From date"
        />
        <input
          type="date"
          value={createdBefore}
          onChange={(event) => setFilter('created_before', event.target.value)}
          aria-label="To date"
        />
      </div>

      {error ? <ErrorNote message={error} onRetry={reload} /> : null}
      {loading && items.length === 0 ? <Spinner /> : null}

      {!loading && items.length === 0 && !error ? (
        <EmptyState title="No stock movements match this view" hint="Try widening the date range." />
      ) : null}

      {items.length > 0 ? (
        <div className="table-wrap">
          <table className="sketch-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Product</th>
                <th>Type</th>
                <th className="num">Qty</th>
                <th>Reason</th>
                <th>Reference</th>
                <th className="num">Balance after</th>
                <th>By</th>
              </tr>
            </thead>
            <tbody>
              {items.map((movement) => (
                <tr key={movement.id}>
                  <td className="nowrap">{dateTime(movement.created_at)}</td>
                  <td>
                    <Link to={`/products/${movement.product}`}>
                      <span className="mono">{movement.product_sku}</span>
                    </Link>
                    <div className="muted" style={{ fontSize: '0.95rem' }}>
                      {movement.product_name}
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${movement.movement_type === 'IN' ? 'badge-ok' : 'badge-info'}`}>
                      {movement.movement_type}
                    </span>
                  </td>
                  <td className="num">
                    {movement.movement_type === 'IN' ? '+' : '-'}
                    {movement.quantity}
                  </td>
                  <td className="nowrap">{movement.reason_display}</td>
                  <td className="mono">{movement.reference || '-'}</td>
                  <td className="num">{movement.balance_after}</td>
                  <td className="nowrap">{movement.created_by_name ?? 'system'}</td>
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
