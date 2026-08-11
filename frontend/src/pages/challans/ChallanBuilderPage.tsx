import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { challans, customers, products } from '../../api/endpoints';
import type { ChallanPayload, CustomerOption, ProductOption, StockShortage } from '../../api/types';
import { useToast } from '../../components/Toast';
import { ErrorNote, PageHeader, Spinner, TextArea, TextInput } from '../../components/ui';
import { useApiResource } from '../../hooks/useApiResource';
import { useDebounce } from '../../hooks/useDebounce';
import { money, today } from '../../utils/format';

interface Line {
  key: string;
  productId: number;
  sku: string;
  name: string;
  unit: string;
  catalogPrice: string;
  price: string;
  available: number;
  quantity: string;
}

let lineCounter = 0;
const newKey = () => `line-${++lineCounter}`;

export function ChallanBuilderPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const toast = useToast();
  const [searchParams] = useSearchParams();

  const [customerId, setCustomerId] = useState<number | null>(
    searchParams.get('customer') ? Number(searchParams.get('customer')) : null,
  );
  const [customerLabel, setCustomerLabel] = useState('');
  const [customerSearch, setCustomerSearch] = useState('');
  const debouncedCustomerSearch = useDebounce(customerSearch);

  const [challanDate, setChallanDate] = useState(today());
  const [notes, setNotes] = useState('');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [vehicleNumber, setVehicleNumber] = useState('');

  const [lines, setLines] = useState<Line[]>([]);
  const [productSearch, setProductSearch] = useState('');
  const debouncedProductSearch = useDebounce(productSearch);

  const [formError, setFormError] = useState<string | null>(null);
  const [shortages, setShortages] = useState<StockShortage[]>([]);
  const [saving, setSaving] = useState<'draft' | 'confirm' | null>(null);

  // -- data ---------------------------------------------------------------
  const existing = useApiResource(
    (signal) => (isEdit ? challans.get(Number(id), signal) : Promise.resolve(null)),
    [id],
  );

  const customerOptions = useApiResource(
    (signal) => customers.options(debouncedCustomerSearch || undefined, signal),
    [debouncedCustomerSearch],
  );

  const productOptions = useApiResource(
    (signal) => products.options(debouncedProductSearch || undefined, false, signal),
    [debouncedProductSearch],
  );

  // Pre-fill from an existing draft.
  useEffect(() => {
    const record = existing.data;
    if (!record) return;
    setCustomerId(record.customer);
    setCustomerLabel(`${record.customer_name}${record.customer_mobile ? ` - ${record.customer_mobile}` : ''}`);
    setChallanDate(record.challan_date);
    setNotes(record.notes);
    setDeliveryAddress(record.delivery_address);
    setVehicleNumber(record.vehicle_number);
    setLines(
      record.items.map((item) => ({
        key: newKey(),
        productId: item.product,
        sku: item.product_sku,
        name: item.product_name,
        unit: item.product_unit,
        catalogPrice: item.unit_price,
        price: item.unit_price,
        available: item.product_stock ?? 0,
        quantity: String(item.quantity),
      })),
    );
  }, [existing.data]);

  // If we arrived with ?customer=, resolve its label for the picker.
  useEffect(() => {
    if (!customerId || customerLabel) return;
    const match = customerOptions.data?.find((option) => option.id === customerId);
    if (match) setCustomerLabel(match.label);
  }, [customerId, customerLabel, customerOptions.data]);

  // -- line helpers -------------------------------------------------------
  const addProduct = (option: ProductOption) => {
    setShortages([]);
    setLines((current) => {
      const existingLine = current.find((line) => line.productId === option.id);
      if (existingLine) {
        // The API rejects duplicate products, so bump the quantity instead.
        toast.info(`${option.sku} is already on the challan - quantity increased.`);
        return current.map((line) =>
          line.productId === option.id
            ? { ...line, quantity: String(Number(line.quantity || '0') + 1) }
            : line,
        );
      }
      return [
        ...current,
        {
          key: newKey(),
          productId: option.id,
          sku: option.sku,
          name: option.name,
          unit: option.unit,
          catalogPrice: option.unit_price,
          price: option.unit_price,
          available: option.current_stock,
          quantity: '1',
        },
      ];
    });
    setProductSearch('');
  };

  const updateLine = (key: string, patch: Partial<Line>) => {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  };

  const removeLine = (key: string) => {
    setLines((current) => current.filter((line) => line.key !== key));
  };

  const totals = useMemo(() => {
    let quantityTotal = 0;
    let amount = 0;
    for (const line of lines) {
      const qty = Number(line.quantity) || 0;
      const price = Number(line.price) || 0;
      quantityTotal += qty;
      amount += qty * price;
    }
    return { quantity: quantityTotal, amount };
  }, [lines]);

  const shortageFor = (productId: number) => shortages.find((s) => s.product_id === productId);

  // -- submit -------------------------------------------------------------
  const submit = async (event: FormEvent, confirm: boolean) => {
    event.preventDefault();
    setFormError(null);
    setShortages([]);

    if (!customerId) {
      setFormError('Choose a customer first.');
      return;
    }
    if (lines.length === 0) {
      setFormError('Add at least one product line.');
      return;
    }
    const invalid = lines.find((line) => !(Number(line.quantity) >= 1));
    if (invalid) {
      setFormError(`Quantity for ${invalid.sku} must be at least 1.`);
      return;
    }

    const payload: ChallanPayload = {
      customer: customerId,
      challan_date: challanDate,
      notes,
      delivery_address: deliveryAddress,
      vehicle_number: vehicleNumber,
      confirm,
      items: lines.map((line) => ({
        product: line.productId,
        quantity: Number(line.quantity),
        // Only send a price when it differs from the catalogue.
        ...(line.price !== line.catalogPrice ? { unit_price: line.price } : {}),
      })),
    };

    setSaving(confirm ? 'confirm' : 'draft');
    try {
      const saved = isEdit
        ? await challans.update(Number(id), payload)
        : await challans.create(payload);

      // PATCH cannot confirm, so do it in a second call when editing.
      if (isEdit && confirm) {
        const confirmed = await challans.confirm(saved.id);
        toast.success(`${confirmed.challan_number} confirmed - stock deducted.`);
        navigate(`/challans/${confirmed.id}`, { replace: true });
        return;
      }

      toast.success(
        confirm
          ? `${saved.challan_number} confirmed - stock deducted.`
          : `${saved.challan_number} saved as a draft.`,
      );
      navigate(`/challans/${saved.id}`, { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message);
        const rows = error.details?.shortages;
        if (Array.isArray(rows)) setShortages(rows as StockShortage[]);
      } else {
        setFormError('Could not reach the server.');
      }
    } finally {
      setSaving(null);
    }
  };

  if (isEdit && existing.loading) return <Spinner label="Loading challan..." />;
  if (isEdit && existing.error) return <ErrorNote message={existing.error} onRetry={existing.reload} />;
  if (isEdit && existing.data && !existing.data.is_editable) {
    return (
      <div className="card">
        <h2>This challan can no longer be edited</h2>
        <p className="muted">
          {existing.data.challan_number} is {existing.data.status_display.toLowerCase()}. Confirmed
          documents are immutable - cancel it and raise a new one instead.
        </p>
        <Link to={`/challans/${id}`} className="btn btn-accent" style={{ marginTop: 16 }}>
          Back to the challan
        </Link>
      </div>
    );
  }

  return (
    <div className="fade-in">
      <PageHeader
        title={isEdit ? `Edit ${existing.data?.challan_number ?? 'challan'}` : 'New sales challan'}
        subtitle="Stock is only deducted when the challan is confirmed."
        actions={
          <Link to={isEdit ? `/challans/${id}` : '/challans'} className="btn">
            Cancel
          </Link>
        }
      />

      {formError ? <div className="alert alert-error">{formError}</div> : null}

      {shortages.length > 0 ? (
        <div className="alert alert-warning">
          <strong>Not enough stock for these lines:</strong>
          <ul>
            {shortages.map((shortage) => (
              <li key={shortage.product_id}>
                <span className="mono">{shortage.sku}</span> - asked for {shortage.requested}, only{' '}
                {shortage.available} on hand (short by {shortage.short_by})
              </li>
            ))}
          </ul>
          <p style={{ marginTop: 8 }}>
            Reduce the quantities, or save it as a draft and let the warehouse restock first.
          </p>
        </div>
      ) : null}

      <form onSubmit={(event) => submit(event, false)}>
        <div className="card">
          <h3>Customer</h3>

          {customerId && customerLabel ? (
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div>
                <strong style={{ fontSize: '1.2rem' }}>{customerLabel}</strong>
              </div>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => {
                  setCustomerId(null);
                  setCustomerLabel('');
                }}
              >
                Change
              </button>
            </div>
          ) : (
            <>
              <TextInput
                name="customer_search"
                label="Search customers"
                value={customerSearch}
                onChange={setCustomerSearch}
                placeholder="Name, business, mobile or code..."
              />
              <div className="stack" style={{ maxHeight: 260, overflowY: 'auto' }}>
                {customerOptions.loading ? <Spinner label="Searching..." /> : null}
                {(customerOptions.data ?? []).map((option: CustomerOption) => (
                  <button
                    key={option.id}
                    type="button"
                    className="btn btn-sm"
                    style={{ textAlign: 'left' }}
                    onClick={() => {
                      setCustomerId(option.id);
                      setCustomerLabel(option.label);
                      setFormError(null);
                    }}
                  >
                    <strong>{option.name}</strong>
                    <span className="muted">
                      {' '}
                      &middot; {option.mobile}
                      {option.business_name ? ` · ${option.business_name}` : ''}
                    </span>
                  </button>
                ))}
                {!customerOptions.loading && (customerOptions.data ?? []).length === 0 ? (
                  <p className="muted">No matching customers.</p>
                ) : null}
              </div>
            </>
          )}

          <hr className="hr-sketch" />

          <div className="form-grid">
            <TextInput
              name="challan_date"
              label="Challan date"
              type="date"
              value={challanDate}
              onChange={setChallanDate}
              required
            />
            <TextInput
              name="vehicle_number"
              label="Vehicle number"
              value={vehicleNumber}
              onChange={setVehicleNumber}
              placeholder="MH-01-AB-1234"
            />
            <TextArea
              name="delivery_address"
              label="Delivery address"
              value={deliveryAddress}
              onChange={setDeliveryAddress}
              className="span-2"
              rows={2}
              hint="Leave blank to deliver to the customer's registered address."
            />
            <TextArea name="notes" label="Notes" value={notes} onChange={setNotes} className="span-2" rows={2} />
          </div>
        </div>

        <div className="card">
          <h3>Products</h3>

          <TextInput
            name="product_search"
            label="Add a product"
            value={productSearch}
            onChange={setProductSearch}
            placeholder="Search by name, SKU or category..."
          />

          {productSearch ? (
            <div className="stack" style={{ maxHeight: 260, overflowY: 'auto', marginBottom: 20 }}>
              {productOptions.loading ? <Spinner label="Searching..." /> : null}
              {(productOptions.data ?? []).map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className="btn btn-sm"
                  style={{ textAlign: 'left' }}
                  onClick={() => addProduct(option)}
                >
                  <span className="mono">{option.sku}</span> &middot; {option.name}
                  <span className={option.current_stock > 0 ? 'muted' : ''}>
                    {' '}
                    &middot; {option.current_stock} in stock &middot; {money(option.unit_price)}
                  </span>
                </button>
              ))}
              {!productOptions.loading && (productOptions.data ?? []).length === 0 ? (
                <p className="muted">No matching products.</p>
              ) : null}
            </div>
          ) : null}

          {lines.length === 0 ? (
            <p className="muted">No lines yet. Search above to add products.</p>
          ) : (
            <div className="table-wrap">
              <table className="sketch-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th className="num">In stock</th>
                    <th className="num">Quantity</th>
                    <th className="num">Unit price</th>
                    <th className="num">Line total</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line) => {
                    const shortage = shortageFor(line.productId);
                    const qty = Number(line.quantity) || 0;
                    const overStock = qty > line.available;
                    return (
                      <tr key={line.key} style={shortage ? { background: 'var(--danger-bg)' } : undefined}>
                        <td>
                          <span className="mono">{line.sku}</span>
                          <div className="muted" style={{ fontSize: '0.95rem' }}>
                            {line.name}
                          </div>
                        </td>
                        <td className="num">
                          <span className={line.available > 0 ? '' : 'badge badge-danger'}>
                            {line.available}
                          </span>
                        </td>
                        <td className="num">
                          <input
                            type="number"
                            min={1}
                            value={line.quantity}
                            onChange={(event) => updateLine(line.key, { quantity: event.target.value })}
                            style={{ width: 100, padding: '6px 10px' }}
                            aria-label={`Quantity for ${line.sku}`}
                          />
                          {overStock ? (
                            <div style={{ fontSize: '0.9rem', color: 'var(--warn-color)' }}>
                              over stock
                            </div>
                          ) : null}
                        </td>
                        <td className="num">
                          <input
                            type="number"
                            min={0}
                            step="0.01"
                            value={line.price}
                            onChange={(event) => updateLine(line.key, { price: event.target.value })}
                            style={{ width: 120, padding: '6px 10px' }}
                            aria-label={`Unit price for ${line.sku}`}
                          />
                          {line.price !== line.catalogPrice ? (
                            <div className="muted" style={{ fontSize: '0.9rem' }}>
                              list {money(line.catalogPrice)}
                            </div>
                          ) : null}
                        </td>
                        <td className="num nowrap">
                          {money((Number(line.quantity) || 0) * (Number(line.price) || 0))}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-sm btn-danger"
                            onClick={() => removeLine(line.key)}
                            aria-label={`Remove ${line.sku}`}
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr>
                    <th colSpan={2}>Totals (before tax)</th>
                    <th className="num">{totals.quantity}</th>
                    <th />
                    <th className="num">{money(totals.amount)}</th>
                    <th />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div className="muted">Total quantity</div>
              <div style={{ fontSize: '1.6rem' }}>{totals.quantity}</div>
            </div>
            <div className="text-right">
              <div className="muted">Value before tax</div>
              <div style={{ fontSize: '1.6rem' }}>{money(totals.amount)}</div>
              <div className="muted" style={{ fontSize: '0.95rem' }}>
                GST is added by the server from each product's rate.
              </div>
            </div>
          </div>

          <hr className="hr-sketch" />

          <div className="row row-end">
            <Link to={isEdit ? `/challans/${id}` : '/challans'} className="btn">
              Cancel
            </Link>
            <button type="submit" className="btn" disabled={saving !== null}>
              {saving === 'draft' ? 'Saving...' : 'Save as draft'}
            </button>
            <button
              type="button"
              className="btn btn-accent"
              disabled={saving !== null}
              onClick={(event) => submit(event, true)}
            >
              {saving === 'confirm' ? 'Confirming...' : 'Save & confirm (deducts stock)'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
