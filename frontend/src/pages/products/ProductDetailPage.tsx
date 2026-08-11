import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { products, stock } from '../../api/endpoints';
import { IfAllowed } from '../../auth/guards';
import { useToast } from '../../components/Toast';
import {
  EmptyState,
  ErrorNote,
  Modal,
  PageHeader,
  SelectInput,
  Spinner,
  StockBadge,
  TextArea,
  TextInput,
} from '../../components/ui';
import { useApiResource, usePaginatedResource } from '../../hooks/useApiResource';
import { dateTime, money, quantity } from '../../utils/format';

const MOVE_REASONS = [
  { value: 'PURCHASE', label: 'Purchase received' },
  { value: 'SALES_RETURN', label: 'Sales return' },
  { value: 'PURCHASE_RETURN', label: 'Purchase return' },
  { value: 'DAMAGE', label: 'Damaged / expired' },
  { value: 'ADJUSTMENT', label: 'Manual adjustment' },
  { value: 'TRANSFER', label: 'Warehouse transfer' },
  { value: 'OPENING', label: 'Opening balance' },
];

export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const productId = Number(id);
  const toast = useToast();

  const [showMove, setShowMove] = useState(false);
  const [showAdjust, setShowAdjust] = useState(false);
  const [busy, setBusy] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const [moveType, setMoveType] = useState<'IN' | 'OUT'>('IN');
  const [moveQty, setMoveQty] = useState('1');
  const [moveReason, setMoveReason] = useState('PURCHASE');
  const [moveReference, setMoveReference] = useState('');
  const [moveNotes, setMoveNotes] = useState('');

  const [countedQty, setCountedQty] = useState('0');
  const [adjustNotes, setAdjustNotes] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadingImage, setUploadingImage] = useState(false);

  const { data: product, loading, error, reload } = useApiResource(
    (signal) => products.get(productId, signal),
    [productId],
  );

  const movements = usePaginatedResource(
    (signal) => products.movements(productId, { page_size: 25 }, signal),
    [productId, product?.current_stock],
  );

  const submitMovement = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setModalError(null);
    try {
      await stock.create({
        product: productId,
        movement_type: moveType,
        quantity: Number(moveQty),
        reason: moveReason,
        reference: moveReference,
        notes: moveNotes,
      });
      toast.success(`Stock ${moveType === 'IN' ? 'added' : 'removed'}.`);
      setShowMove(false);
      setMoveQty('1');
      setMoveReference('');
      setMoveNotes('');
      reload();
    } catch (err) {
      setModalError(err instanceof ApiError ? err.message : 'Could not record the movement.');
    } finally {
      setBusy(false);
    }
  };

  const submitAdjustment = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setModalError(null);
    try {
      await products.adjustStock(productId, Number(countedQty), adjustNotes);
      toast.success('Stock corrected.');
      setShowAdjust(false);
      setAdjustNotes('');
      reload();
    } catch (err) {
      setModalError(err instanceof ApiError ? err.message : 'Could not adjust the stock.');
    } finally {
      setBusy(false);
    }
  };

  const onImagePicked = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow re-picking the same file
    if (!file) return;

    setUploadingImage(true);
    try {
      await products.uploadImage(productId, file);
      toast.success('Product image updated.');
      reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not upload the image.');
    } finally {
      setUploadingImage(false);
    }
  };

  const removeImage = async () => {
    setUploadingImage(true);
    try {
      await products.deleteImage(productId);
      toast.info('Product image removed.');
      reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not remove the image.');
    } finally {
      setUploadingImage(false);
    }
  };

  if (loading && !product) return <Spinner label="Loading product..." />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!product) return null;

  return (
    <div className="fade-in">
      <PageHeader
        title={product.name}
        subtitle={
          <span className="row" style={{ gap: 8 }}>
            <span className="mono">{product.sku}</span>
            <span className="badge badge-muted">{product.category}</span>
            {!product.is_active ? <span className="badge badge-danger">Archived</span> : null}
          </span>
        }
        actions={
          <>
            <Link to="/products" className="btn">
              Back
            </Link>
            <IfAllowed capability="stock.write">
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setCountedQty(String(product.current_stock));
                  setModalError(null);
                  setShowAdjust(true);
                }}
              >
                Stock-take
              </button>
              <button
                type="button"
                className="btn btn-accent"
                onClick={() => {
                  setModalError(null);
                  setShowMove(true);
                }}
              >
                + Stock movement
              </button>
            </IfAllowed>
            <IfAllowed capability="products.write">
              <Link to={`/products/${product.id}/edit`} className="btn">
                Edit
              </Link>
            </IfAllowed>
          </>
        }
      />

      {product.is_out_of_stock ? (
        <div className="alert alert-error">This product is out of stock - challans for it will be refused.</div>
      ) : product.is_low_stock ? (
        <div className="alert alert-warning">
          Stock is at or below the alert level ({product.current_stock} of {product.min_stock_alert}).
        </div>
      ) : null}

      <div className="overview-grid">
        <div className="overview-card">
          <div className="overview-label">On hand</div>
          <div className="overview-value">
            {quantity(product.current_stock)} <span style={{ fontSize: '1rem' }}>{product.unit_display}</span>
          </div>
          <div style={{ marginTop: 8 }}>
            <StockBadge stock={product.current_stock} minAlert={product.min_stock_alert} />
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-label">Unit price</div>
          <div className="overview-value">{money(product.unit_price)}</div>
          <div className="muted" style={{ fontSize: '0.95rem', marginTop: 6 }}>
            GST {product.tax_rate}%
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-label">Stock value</div>
          <div className="overview-value">{money(product.stock_value)}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        <section className="card">
          <h3>Photo</h3>
          <div
            className="image-preview-wrapper"
            style={{ width: '100%', height: 220, borderRadius: 'var(--border-radius-2)', cursor: 'pointer' }}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter') fileInputRef.current?.click();
            }}
          >
            {product.image_url ? (
              <img src={product.image_url} alt={product.name} className="preview-img" />
            ) : (
              <div className="placeholder-icon">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
              </div>
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            style={{ display: 'none' }}
            onChange={onImagePicked}
          />

          <p className="muted" style={{ fontSize: '0.95rem', marginTop: 8 }}>
            JPEG, PNG or WebP up to 5 MB. Stored on S3 when <span className="mono">USE_S3</span> is
            enabled, on the local media volume otherwise.
          </p>

          <IfAllowed capability="products.write">
            <div className="row" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingImage}
              >
                {uploadingImage ? 'Uploading...' : product.image_url ? 'Replace image' : 'Upload image'}
              </button>
              {product.image_url ? (
                <button
                  type="button"
                  className="btn btn-sm btn-danger"
                  onClick={removeImage}
                  disabled={uploadingImage}
                >
                  Remove
                </button>
              ) : null}
            </div>
          </IfAllowed>
        </section>

        <section className="card">
          <h3>Details</h3>
          <table className="credential-table">
            <tbody>
              <tr>
                <td className="muted">Location</td>
                <td>{product.location || '-'}</td>
              </tr>
              <tr>
                <td className="muted">Alert level</td>
                <td>{product.min_stock_alert}</td>
              </tr>
              <tr>
                <td className="muted">HSN code</td>
                <td className="mono">{product.hsn_code || '-'}</td>
              </tr>
              <tr>
                <td className="muted">Added by</td>
                <td>{product.created_by_name ?? '-'}</td>
              </tr>
              <tr>
                <td className="muted">Last updated</td>
                <td>{dateTime(product.updated_at)}</td>
              </tr>
            </tbody>
          </table>
          {product.description ? (
            <>
              <hr className="hr-sketch" />
              <p style={{ whiteSpace: 'pre-wrap' }}>{product.description}</p>
            </>
          ) : null}
        </section>

        <section className="card">
          <h3>How stock changed</h3>
          <p className="muted">
            Every row below is an immutable ledger entry. The balance column is the stock on hand right
            after that movement, so the two can always be reconciled.
          </p>
          <p className="muted" style={{ marginTop: 10 }}>
            Sales challans write their own <span className="mono">SALE</span> rows on confirmation - they
            cannot be entered by hand.
          </p>
        </section>
      </div>

      <section className="card">
        <h3>Stock movement log</h3>
        {movements.loading && movements.items.length === 0 ? <Spinner label="Loading ledger..." /> : null}
        {!movements.loading && movements.items.length === 0 ? (
          <EmptyState title="No stock has moved yet" />
        ) : null}

        {movements.items.length > 0 ? (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="sketch-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Type</th>
                  <th className="num">Qty</th>
                  <th>Reason</th>
                  <th>Reference</th>
                  <th className="num">Balance</th>
                  <th>By</th>
                </tr>
              </thead>
              <tbody>
                {movements.items.map((movement) => (
                  <tr key={movement.id}>
                    <td className="nowrap">{dateTime(movement.created_at)}</td>
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
      </section>

      {showMove ? (
        <Modal
          title="Record a stock movement"
          onClose={() => setShowMove(false)}
          footer={
            <>
              <button type="button" className="btn" onClick={() => setShowMove(false)}>
                Cancel
              </button>
              <button type="submit" form="move-form" className="btn btn-accent" disabled={busy}>
                {busy ? 'Saving...' : 'Record movement'}
              </button>
            </>
          }
        >
          <form id="move-form" onSubmit={submitMovement}>
            {modalError ? <div className="alert alert-error">{modalError}</div> : null}
            <p className="muted" style={{ marginBottom: 14 }}>
              Currently on hand: <strong>{product.current_stock}</strong> {product.unit_display}
            </p>
            <div className="form-grid">
              <SelectInput
                name="movement_type"
                label="Direction"
                value={moveType}
                onChange={(value) => setMoveType(value as 'IN' | 'OUT')}
                options={[
                  { value: 'IN', label: 'Stock in (+)' },
                  { value: 'OUT', label: 'Stock out (-)' },
                ]}
                required
              />
              <TextInput
                name="quantity"
                label="Quantity"
                type="number"
                min={1}
                value={moveQty}
                onChange={setMoveQty}
                required
              />
              <SelectInput
                name="reason"
                label="Reason"
                value={moveReason}
                onChange={setMoveReason}
                options={MOVE_REASONS}
                required
              />
              <TextInput
                name="reference"
                label="Reference"
                value={moveReference}
                onChange={setMoveReference}
                placeholder="PO-2026-0043"
              />
            </div>
            <TextArea name="notes" label="Notes" value={moveNotes} onChange={setMoveNotes} rows={2} />
          </form>
        </Modal>
      ) : null}

      {showAdjust ? (
        <Modal
          title="Stock-take correction"
          onClose={() => setShowAdjust(false)}
          footer={
            <>
              <button type="button" className="btn" onClick={() => setShowAdjust(false)}>
                Cancel
              </button>
              <button type="submit" form="adjust-form" className="btn btn-accent" disabled={busy}>
                {busy ? 'Saving...' : 'Correct stock'}
              </button>
            </>
          }
        >
          <form id="adjust-form" onSubmit={submitAdjustment}>
            {modalError ? <div className="alert alert-error">{modalError}</div> : null}
            <p className="muted" style={{ marginBottom: 14 }}>
              System says <strong>{product.current_stock}</strong>. Enter what you actually counted - the
              difference is logged as an ADJUSTMENT movement.
            </p>
            <TextInput
              name="new_quantity"
              label="Counted quantity"
              type="number"
              min={0}
              value={countedQty}
              onChange={setCountedQty}
              required
            />
            <TextArea
              name="adjust_notes"
              label="Why the difference?"
              value={adjustNotes}
              onChange={setAdjustNotes}
              rows={2}
              placeholder="Two tins found damaged during the monthly count."
            />
          </form>
        </Modal>
      ) : null}
    </div>
  );
}
