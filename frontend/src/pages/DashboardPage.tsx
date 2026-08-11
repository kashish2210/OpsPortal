import { Link } from 'react-router-dom';

import { dashboard } from '../api/endpoints';
import { useAuth } from '../auth/AuthContext';
import { IfAllowed } from '../auth/guards';
import {
  ChallanStatusBadge,
  EmptyState,
  ErrorNote,
  PageHeader,
  Spinner,
  StatTile,
} from '../components/ui';
import { useApiResource } from '../hooks/useApiResource';
import { date, money, quantity, relativeDays } from '../utils/format';

export function DashboardPage() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useApiResource((signal) => dashboard.summary(signal), []);

  if (loading && !data) return <Spinner label="Loading your dashboard..." />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!data) return null;

  const { customers, inventory, sales } = data;
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  return (
    <div className="fade-in">
      <PageHeader
        title={`${greeting}, ${user?.first_name || user?.username}`}
        subtitle={`${user?.role_display} view · updated ${new Date(data.generated_at).toLocaleTimeString('en-IN')}`}
        actions={
          <>
            <IfAllowed capability="challans.write">
              <Link to="/challans/new" className="btn btn-accent">
                + New challan
              </Link>
            </IfAllowed>
            <IfAllowed capability="customers.write">
              <Link to="/customers/new" className="btn">
                + New customer
              </Link>
            </IfAllowed>
          </>
        }
      />

      {inventory.out_of_stock > 0 || customers.follow_ups_due > 0 ? (
        <div className="dashboard-alert">
          {inventory.out_of_stock > 0 ? (
            <div>
              <strong>{inventory.out_of_stock}</strong> product
              {inventory.out_of_stock === 1 ? ' is' : 's are'} out of stock.{' '}
              <Link to="/products?stock=out">Review them</Link>
            </div>
          ) : null}
          {customers.follow_ups_due > 0 ? (
            <div>
              <strong>{customers.follow_ups_due}</strong> customer follow-up
              {customers.follow_ups_due === 1 ? ' is' : 's are'} due.{' '}
              <Link to="/customers?follow_up=due">Open the list</Link>
            </div>
          ) : null}
        </div>
      ) : null}

      <h2 className="recent-title">Customers</h2>
      <div className="overview-grid">
        <StatTile label="Total customers" value={quantity(customers.total)} hint={`${customers.added_this_month} added this month`} />
        <StatTile label="Active" value={quantity(customers.active)} />
        <StatTile label="Open leads" value={quantity(customers.leads)} tone={customers.leads > 0 ? 'warn' : undefined} />
      </div>

      <h2 className="recent-title">Inventory</h2>
      <div className="overview-grid">
        <StatTile label="Products" value={quantity(inventory.active_products)} hint={`${inventory.total_products} including archived`} />
        <StatTile
          label="Low stock"
          value={quantity(inventory.low_stock)}
          tone={inventory.low_stock > 0 ? 'warn' : undefined}
          hint={`${inventory.out_of_stock} out of stock`}
        />
        <StatTile label="Stock value" value={money(inventory.stock_value)} hint={`${quantity(inventory.total_stock_units)} units on hand`} />
      </div>

      <h2 className="recent-title">Sales challans</h2>
      <div className="overview-grid">
        <StatTile label="Confirmed" value={quantity(sales.confirmed)} hint={`${sales.draft} draft · ${sales.cancelled} cancelled`} />
        <StatTile label="Units shipped" value={quantity(sales.units_shipped)} />
        <StatTile label="This month" value={money(sales.this_month_value)} hint={`${money(sales.confirmed_value)} all time`} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 20 }}>
        <section className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h3>Recent challans</h3>
            <Link to="/challans" className="btn btn-sm">
              View all
            </Link>
          </div>
          {data.recent_challans.length === 0 ? (
            <EmptyState title="No challans yet" hint="Raise one from the Sales challans screen." />
          ) : (
            <ul className="activity-list">
              {data.recent_challans.map((challan) => (
                <li key={challan.id}>
                  <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                    <Link to={`/challans/${challan.id}`} className="mono">
                      {challan.challan_number}
                    </Link>
                    <ChallanStatusBadge status={challan.status} label={challan.status_display} />
                  </div>
                  <div className="muted" style={{ fontSize: '1rem' }}>
                    {challan.customer_name} &middot; {money(challan.grand_total)} &middot;{' '}
                    {date(challan.challan_date)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h3>Low stock</h3>
            <Link to="/products?stock=low" className="btn btn-sm">
              View all
            </Link>
          </div>
          {data.low_stock_products.length === 0 ? (
            <EmptyState title="Everything is above its alert level" />
          ) : (
            <ul className="activity-list">
              {data.low_stock_products.map((product) => (
                <li key={product.id}>
                  <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                    <Link to={`/products/${product.id}`}>{product.name}</Link>
                    <span className={`badge ${product.current_stock <= 0 ? 'badge-danger' : 'badge-warn'}`}>
                      {product.current_stock} / {product.min_stock_alert}
                    </span>
                  </div>
                  <div className="muted" style={{ fontSize: '1rem' }}>
                    <span className="mono">{product.sku}</span> &middot; {product.location || 'No location'}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h3>Follow-ups due</h3>
            <Link to="/customers?follow_up=due" className="btn btn-sm">
              View all
            </Link>
          </div>
          {data.follow_ups_due.length === 0 ? (
            <EmptyState title="Nothing due today" hint="Nice - the CRM is clear." />
          ) : (
            <ul className="activity-list">
              {data.follow_ups_due.map((customer) => (
                <li key={customer.id}>
                  <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                    <Link to={`/customers/${customer.id}`}>{customer.name}</Link>
                    <span className="badge badge-warn">{relativeDays(customer.follow_up_date)}</span>
                  </div>
                  <div className="muted" style={{ fontSize: '1rem' }}>
                    {customer.business_name || customer.customer_type_display} &middot; {customer.mobile}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h3>Latest stock movements</h3>
            <Link to="/stock" className="btn btn-sm">
              View log
            </Link>
          </div>
          {data.recent_movements.length === 0 ? (
            <EmptyState title="No stock has moved yet" />
          ) : (
            <ul className="activity-list">
              {data.recent_movements.map((movement) => (
                <li key={movement.id}>
                  <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                    <span className="mono">{movement.product_sku}</span>
                    <span className={`badge ${movement.movement_type === 'IN' ? 'badge-ok' : 'badge-info'}`}>
                      {movement.movement_type === 'IN' ? '+' : '-'}
                      {movement.quantity}
                    </span>
                  </div>
                  <div className="muted" style={{ fontSize: '1rem' }}>
                    {movement.reason_display}
                    {movement.reference ? ` · ${movement.reference}` : ''} &middot;{' '}
                    {movement.created_by_name ?? 'system'}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
