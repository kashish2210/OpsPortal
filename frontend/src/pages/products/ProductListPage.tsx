import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { products } from '../../api/endpoints';
import { IfAllowed } from '../../auth/guards';
import {
  EmptyState,
  ErrorNote,
  PageHeader,
  Pagination,
  Spinner,
  StockBadge,
} from '../../components/ui';
import { useApiResource, usePaginatedResource } from '../../hooks/useApiResource';
import { useDebounce } from '../../hooks/useDebounce';
import { money } from '../../utils/format';

const STOCK_OPTIONS = [
  { value: '', label: 'Any stock level' },
  { value: 'low', label: 'At or below alert' },
  { value: 'out', label: 'Out of stock' },
  { value: 'in', label: 'In stock' },
];

export function ProductListPage() {
  const [params, setParams] = useSearchParams();

  const [search, setSearch] = useState(params.get('q') ?? '');
  const debouncedSearch = useDebounce(search);

  const category = params.get('category') ?? '';
  const stockLevel = params.get('stock') ?? '';
  const isActive = params.get('is_active') ?? 'true';
  const ordering = params.get('ordering') ?? 'name';
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

  const categories = useApiResource((signal) => products.categories(signal), []);

  const { items, count, totalPages, loading, error, reload } = usePaginatedResource(
    (signal) =>
      products.list(
        {
          q: debouncedSearch || undefined,
          category: category || undefined,
          stock: stockLevel || undefined,
          is_active: isActive || undefined,
          ordering,
          page,
        },
        signal,
      ),
    [debouncedSearch, category, stockLevel, isActive, ordering, page],
  );

  return (
    <div className="fade-in">
      <PageHeader
        title="Products"
        subtitle="Catalogue and live stock balances. Stock only changes through the movement log."
        actions={
          <IfAllowed capability="products.write">
            <Link to="/products/new" className="btn btn-accent">
              + Add product
            </Link>
          </IfAllowed>
        }
      />

      <div className="toolbar">
        <input
          className="grow"
          type="search"
          placeholder="Search name, SKU, category, HSN or location..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search products"
        />
        <select value={category} onChange={(event) => setFilter('category', event.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {(categories.data ?? []).map((row) => (
            <option key={row.category} value={row.category}>
              {row.category} ({row.count})
            </option>
          ))}
        </select>
        <select value={stockLevel} onChange={(event) => setFilter('stock', event.target.value)} aria-label="Stock level">
          {STOCK_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select value={isActive} onChange={(event) => setFilter('is_active', event.target.value)} aria-label="Active">
          <option value="true">Active only</option>
          <option value="false">Archived only</option>
          <option value="">Active + archived</option>
        </select>
        <select value={ordering} onChange={(event) => setFilter('ordering', event.target.value)} aria-label="Sort">
          <option value="name">Name A-Z</option>
          <option value="-name">Name Z-A</option>
          <option value="current_stock">Stock low to high</option>
          <option value="-current_stock">Stock high to low</option>
          <option value="unit_price">Price low to high</option>
          <option value="-unit_price">Price high to low</option>
        </select>
      </div>

      {error ? <ErrorNote message={error} onRetry={reload} /> : null}
      {loading && items.length === 0 ? <Spinner /> : null}

      {!loading && items.length === 0 && !error ? (
        <EmptyState
          title="No products match this view"
          hint="Try a different search or clear the filters."
          action={
            <IfAllowed capability="products.write">
              <Link to="/products/new" className="btn btn-accent">
                Add the first product
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
                <th>SKU</th>
                <th>Product</th>
                <th>Category</th>
                <th className="num">Unit price</th>
                <th className="num">Stock</th>
                <th className="num">Alert at</th>
                <th>Location</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((product) => (
                <tr key={product.id} style={product.is_active ? undefined : { opacity: 0.55 }}>
                  <td className="mono nowrap">{product.sku}</td>
                  <td>
                    <div className="row" style={{ gap: 10, flexWrap: 'nowrap' }}>
                      {product.image_url ? (
                        <img
                          src={product.image_url}
                          alt=""
                          style={{
                            width: 36,
                            height: 36,
                            objectFit: 'cover',
                            border: '2px solid var(--border-color)',
                            borderRadius: 8,
                            flex: '0 0 auto',
                          }}
                        />
                      ) : null}
                      <span>
                        <Link to={`/products/${product.id}`}>
                          <strong>{product.name}</strong>
                        </Link>
                        {!product.is_active ? (
                          <span className="badge badge-muted" style={{ marginLeft: 8 }}>
                            Archived
                          </span>
                        ) : null}
                      </span>
                    </div>
                  </td>
                  <td className="nowrap">{product.category}</td>
                  <td className="num nowrap">{money(product.unit_price)}</td>
                  <td className="num">
                    <StockBadge stock={product.current_stock} minAlert={product.min_stock_alert} />
                  </td>
                  <td className="num">{product.min_stock_alert}</td>
                  <td>{product.location || '-'}</td>
                  <td className="nowrap">
                    <Link to={`/products/${product.id}`} className="btn btn-sm">
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
