import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { challans } from '../../api/endpoints';
import type { StockShortage } from '../../api/types';
import { IfAllowed } from '../../auth/guards';
import { useToast } from '../../components/Toast';
import {
  ChallanStatusBadge,
  ErrorNote,
  Modal,
  PageHeader,
  Spinner,
  TextArea,
} from '../../components/ui';
import { useApiResource } from '../../hooks/useApiResource';
import { date, dateTime, money } from '../../utils/format';

export function ChallanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const challanId = Number(id);
  const navigate = useNavigate();
  const toast = useToast();

  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [shortages, setShortages] = useState<StockShortage[]>([]);
  const [showCancel, setShowCancel] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [downloading, setDownloading] = useState(false);

  const { data: challan, loading, error, reload } = useApiResource(
    (signal) => challans.get(challanId, signal),
    [challanId],
  );

  const movements = useApiResource(
    (signal) => challans.stockMovements(challanId, signal),
    [challanId, challan?.status],
  );

  const confirm = async () => {
    setBusy(true);
    setActionError(null);
    setShortages([]);
    try {
      await challans.confirm(challanId);
      toast.success('Challan confirmed - stock deducted.');
      reload();
    } catch (err) {
      if (err instanceof ApiError) {
        setActionError(err.message);
        const rows = err.details?.shortages;
        if (Array.isArray(rows)) setShortages(rows as StockShortage[]);
      } else {
        setActionError('Could not reach the server.');
      }
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    setBusy(true);
    setActionError(null);
    try {
      await challans.cancel(challanId, cancelReason);
      toast.info('Challan cancelled.');
      setShowCancel(false);
      setCancelReason('');
      reload();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not cancel the challan.');
    } finally {
      setBusy(false);
    }
  };

  const downloadPdf = async (inline: boolean) => {
    if (!challan) return;
    setDownloading(true);
    try {
      await challans.downloadPdf(challan.id, challan.challan_number, inline);
      if (!inline) toast.success(`${challan.challan_number}.pdf downloaded.`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not generate the PDF.');
    } finally {
      setDownloading(false);
    }
  };

  const remove = async () => {
    if (!window.confirm('Delete this draft challan? This cannot be undone.')) return;
    setBusy(true);
    try {
      await challans.remove(challanId);
      toast.info('Draft deleted.');
      navigate('/challans', { replace: true });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not delete the draft.');
      setBusy(false);
    }
  };

  if (loading && !challan) return <Spinner label="Loading challan..." />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!challan) return null;

  return (
    <div className="fade-in">
      <PageHeader
        title={challan.challan_number}
        subtitle={
          <span className="row" style={{ gap: 8 }}>
            <ChallanStatusBadge status={challan.status} label={challan.status_display} />
            <span className="muted">{date(challan.challan_date)}</span>
          </span>
        }
        actions={
          <>
            <Link to="/challans" className="btn">
              Back
            </Link>
            <button type="button" className="btn" onClick={() => downloadPdf(true)} disabled={downloading}>
              Preview PDF
            </button>
            <button type="button" className="btn" onClick={() => downloadPdf(false)} disabled={downloading}>
              {downloading ? 'Generating...' : 'Download PDF'}
            </button>
            <IfAllowed capability="challans.write">
              {challan.is_editable ? (
                <>
                  <Link to={`/challans/${challan.id}/edit`} className="btn">
                    Edit
                  </Link>
                  <button type="button" className="btn btn-accent" onClick={confirm} disabled={busy}>
                    {busy ? 'Working...' : 'Confirm (deduct stock)'}
                  </button>
                </>
              ) : null}
              {challan.can_cancel ? (
                <button type="button" className="btn btn-danger" onClick={() => setShowCancel(true)} disabled={busy}>
                  Cancel challan
                </button>
              ) : null}
              {challan.status === 'DRAFT' ? (
                <button type="button" className="btn btn-sm" onClick={remove} disabled={busy}>
                  Delete draft
                </button>
              ) : null}
            </IfAllowed>
          </>
        }
      />

      {actionError ? <div className="alert alert-error">{actionError}</div> : null}

      {shortages.length > 0 ? (
        <div className="alert alert-warning">
          <strong>Not enough stock to confirm this challan:</strong>
          <ul>
            {shortages.map((shortage) => (
              <li key={shortage.product_id}>
                <span className="mono">{shortage.sku}</span> ({shortage.product_name}) - needs{' '}
                {shortage.requested}, only {shortage.available} on hand (short by {shortage.short_by})
              </li>
            ))}
          </ul>
          <p style={{ marginTop: 8 }}>
            Nothing was deducted. Restock, or edit the challan to reduce the quantities.
          </p>
        </div>
      ) : null}

      {challan.status === 'CANCELLED' ? (
        <div className="alert alert-info">
          Cancelled on {dateTime(challan.cancelled_at)} by {challan.cancelled_by_name ?? 'system'}.
          {challan.cancellation_reason ? ` Reason: ${challan.cancellation_reason}` : ''}
        </div>
      ) : null}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        <section className="card">
          <h3>Billed to</h3>
          <p className="muted" style={{ marginBottom: 10 }}>
            Snapshot taken when the challan was raised - later edits to the customer do not change it.
          </p>
          <table className="credential-table">
            <tbody>
              <tr>
                <td className="muted">Customer</td>
                <td>
                  <Link to={`/customers/${challan.customer}`}>{challan.customer_name}</Link>
                </td>
              </tr>
              <tr>
                <td className="muted">Business</td>
                <td>{challan.customer_business_name || '-'}</td>
              </tr>
              <tr>
                <td className="muted">Mobile</td>
                <td className="mono">{challan.customer_mobile || '-'}</td>
              </tr>
              <tr>
                <td className="muted">GST</td>
                <td className="mono">{challan.customer_gst_number || '-'}</td>
              </tr>
              <tr>
                <td className="muted">Address</td>
                <td>{challan.customer_address || '-'}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="card">
          <h3>Dispatch &amp; audit</h3>
          <table className="credential-table">
            <tbody>
              <tr>
                <td className="muted">Delivery address</td>
                <td>{challan.delivery_address || 'Customer address'}</td>
              </tr>
              <tr>
                <td className="muted">Vehicle</td>
                <td className="mono">{challan.vehicle_number || '-'}</td>
              </tr>
              <tr>
                <td className="muted">Raised by</td>
                <td>
                  {challan.created_by_name ?? '-'} on {dateTime(challan.created_at)}
                </td>
              </tr>
              {challan.confirmed_at ? (
                <tr>
                  <td className="muted">Confirmed by</td>
                  <td>
                    {challan.confirmed_by_name ?? '-'} on {dateTime(challan.confirmed_at)}
                  </td>
                </tr>
              ) : null}
              {challan.cancelled_at ? (
                <tr>
                  <td className="muted">Cancelled by</td>
                  <td>
                    {challan.cancelled_by_name ?? '-'} on {dateTime(challan.cancelled_at)}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          {challan.notes ? (
            <>
              <hr className="hr-sketch" />
              <h4>Notes</h4>
              <p style={{ whiteSpace: 'pre-wrap' }}>{challan.notes}</p>
            </>
          ) : null}
        </section>
      </div>

      <section className="card">
        <h3>Lines</h3>
        <p className="muted" style={{ marginBottom: 12 }}>
          Each line carries a product snapshot, so renaming or repricing a product later never rewrites
          this document.
        </p>
        <div className="table-wrap">
          <table className="sketch-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Product</th>
                <th>Category</th>
                <th className="num">Qty</th>
                <th className="num">Unit price</th>
                <th className="num">Amount</th>
                <th className="num">Tax</th>
              </tr>
            </thead>
            <tbody>
              {challan.items.map((item) => (
                <tr key={item.id ?? `${item.product}-${item.product_sku}`}>
                  <td className="mono nowrap">{item.product_sku}</td>
                  <td>{item.product_name}</td>
                  <td className="nowrap">{item.product_category || '-'}</td>
                  <td className="num">
                    {item.quantity} {item.product_unit}
                  </td>
                  <td className="num nowrap">{money(item.unit_price)}</td>
                  <td className="num nowrap">{money(item.line_total)}</td>
                  <td className="num nowrap">{money(item.line_tax)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th colSpan={3}>Totals</th>
                <th className="num">{challan.total_quantity}</th>
                <th />
                <th className="num">{money(challan.total_amount)}</th>
                <th className="num">{money(challan.total_tax)}</th>
              </tr>
              <tr>
                <th colSpan={6}>Grand total</th>
                <th className="num" style={{ fontSize: '1.2rem' }}>
                  {money(challan.grand_total)}
                </th>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section className="card">
        <h3>Stock movements from this challan</h3>
        {movements.loading ? <Spinner label="Loading ledger..." /> : null}
        {!movements.loading && (movements.data ?? []).length === 0 ? (
          <p className="muted">
            No stock has moved yet - a draft reserves nothing. Confirm the challan to deduct stock.
          </p>
        ) : null}
        {(movements.data ?? []).length > 0 ? (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="sketch-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Product</th>
                  <th>Type</th>
                  <th className="num">Qty</th>
                  <th>Reason</th>
                  <th className="num">Balance after</th>
                  <th>By</th>
                </tr>
              </thead>
              <tbody>
                {(movements.data ?? []).map((movement) => (
                  <tr key={movement.id}>
                    <td className="nowrap">{dateTime(movement.created_at)}</td>
                    <td className="mono">{movement.product_sku}</td>
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
                    <td className="num">{movement.balance_after}</td>
                    <td className="nowrap">{movement.created_by_name ?? 'system'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {showCancel ? (
        <Modal
          title={`Cancel ${challan.challan_number}`}
          onClose={() => setShowCancel(false)}
          footer={
            <>
              <button type="button" className="btn" onClick={() => setShowCancel(false)}>
                Keep it
              </button>
              <button type="button" className="btn btn-danger" onClick={cancel} disabled={busy}>
                {busy ? 'Cancelling...' : 'Cancel challan'}
              </button>
            </>
          }
        >
          <p>
            {challan.status === 'CONFIRMED'
              ? 'This challan is confirmed, so cancelling will return its stock to the warehouse with compensating IN movements.'
              : 'This is a draft, so no stock has moved. Cancelling just closes it off.'}
          </p>
          <TextArea
            name="cancel_reason"
            label="Reason"
            value={cancelReason}
            onChange={setCancelReason}
            rows={3}
            placeholder="Customer cancelled the order before delivery."
          />
        </Modal>
      ) : null}
    </div>
  );
}
