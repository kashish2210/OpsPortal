import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { products } from '../../api/endpoints';
import type { ProductPayload } from '../../api/types';
import { useToast } from '../../components/Toast';
import { ErrorNote, PageHeader, SelectInput, Spinner, TextArea, TextInput } from '../../components/ui';
import { useApiResource } from '../../hooks/useApiResource';

const UNITS = [
  { value: 'PCS', label: 'Pieces' },
  { value: 'BOX', label: 'Box' },
  { value: 'KG', label: 'Kilogram' },
  { value: 'LTR', label: 'Litre' },
  { value: 'MTR', label: 'Metre' },
  { value: 'PKT', label: 'Packet' },
  { value: 'SET', label: 'Set' },
];

const EMPTY: ProductPayload = {
  name: '',
  sku: '',
  category: '',
  description: '',
  unit: 'PCS',
  unit_price: '',
  hsn_code: '',
  tax_rate: '18',
  opening_stock: 0,
  min_stock_alert: 0,
  location: '',
  is_active: true,
};

export function ProductFormPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const toast = useToast();

  const [form, setForm] = useState<ProductPayload>(EMPTY);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const existing = useApiResource(
    (signal) => (isEdit ? products.get(Number(id), signal) : Promise.resolve(null)),
    [id],
  );
  const categories = useApiResource((signal) => products.categories(signal), []);
  const locations = useApiResource((signal) => products.locations(signal), []);

  useEffect(() => {
    const record = existing.data;
    if (!record) return;
    setForm({
      name: record.name,
      sku: record.sku,
      category: record.category,
      description: record.description,
      unit: record.unit,
      unit_price: record.unit_price,
      hsn_code: record.hsn_code,
      tax_rate: record.tax_rate,
      min_stock_alert: record.min_stock_alert,
      location: record.location,
      is_active: record.is_active,
    });
  }, [existing.data]);

  const update = <K extends keyof ProductPayload>(key: K, value: ProductPayload[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => {
      if (!(key in current)) return current;
      const next = { ...current };
      delete next[key as string];
      return next;
    });
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setFormError(null);
    setFieldErrors({});

    // opening_stock is only meaningful on create.
    const payload: ProductPayload = isEdit ? { ...form, opening_stock: undefined } : form;

    try {
      const saved = isEdit ? await products.update(Number(id), payload) : await products.create(payload);
      toast.success(isEdit ? 'Product updated.' : `${saved.name} added.`);
      navigate(`/products/${saved.id}`, { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        setFieldErrors(error.fieldErrors());
        setFormError(error.message);
      } else {
        setFormError('Could not reach the server.');
      }
    } finally {
      setSaving(false);
    }
  };

  if (isEdit && existing.loading) return <Spinner label="Loading product..." />;
  if (isEdit && existing.error) return <ErrorNote message={existing.error} onRetry={existing.reload} />;

  return (
    <div className="fade-in">
      <PageHeader
        title={isEdit ? `Edit ${form.name || 'product'}` : 'Add product'}
        subtitle={
          isEdit
            ? 'Stock cannot be edited here - use the stock log or a stock-take adjustment.'
            : 'Opening stock is recorded as an OPENING movement in the ledger.'
        }
        actions={
          <Link to={isEdit ? `/products/${id}` : '/products'} className="btn">
            Cancel
          </Link>
        }
      />

      <form onSubmit={handleSubmit}>
        {formError ? <div className="alert alert-error">{formError}</div> : null}

        <datalist id="category-options">
          {(categories.data ?? []).map((row) => (
            <option key={row.category} value={row.category} />
          ))}
        </datalist>
        <datalist id="location-options">
          {(locations.data ?? []).map((row) => (
            <option key={row.location} value={row.location} />
          ))}
        </datalist>

        <div className="card">
          <h3>Identity</h3>
          <div className="form-grid">
            <TextInput
              name="name"
              label="Product name"
              value={form.name}
              onChange={(value) => update('name', value)}
              error={fieldErrors.name}
              required
              placeholder="Copper Wire 1.5mm (90m)"
            />
            <TextInput
              name="sku"
              label="SKU / code"
              value={form.sku}
              onChange={(value) => update('sku', value.toUpperCase())}
              error={fieldErrors.sku}
              required
              placeholder="EL-CW15-90"
              hint="Unique. Stored in upper case."
            />
            <TextInput
              name="category"
              label="Category"
              value={form.category}
              onChange={(value) => update('category', value)}
              error={fieldErrors.category}
              required
              list="category-options"
              placeholder="Electrical"
              hint="Pick an existing category or type a new one."
            />
            <TextInput
              name="location"
              label="Location / warehouse"
              value={form.location ?? ''}
              onChange={(value) => update('location', value)}
              error={fieldErrors.location}
              list="location-options"
              placeholder="Warehouse A - Rack 1"
            />
            <TextArea
              name="description"
              label="Description"
              value={form.description ?? ''}
              onChange={(value) => update('description', value)}
              error={fieldErrors.description}
              className="span-2"
            />
          </div>
        </div>

        <div className="card">
          <h3>Pricing</h3>
          <div className="form-grid">
            <SelectInput
              name="unit"
              label="Unit"
              value={form.unit}
              onChange={(value) => update('unit', value)}
              options={UNITS}
              error={fieldErrors.unit}
              required
            />
            <TextInput
              name="unit_price"
              label="Unit price"
              type="number"
              min={0}
              step="0.01"
              value={form.unit_price}
              onChange={(value) => update('unit_price', value)}
              error={fieldErrors.unit_price}
              required
              placeholder="1180.00"
            />
            <TextInput
              name="tax_rate"
              label="GST %"
              type="number"
              min={0}
              step="0.01"
              value={form.tax_rate ?? '0'}
              onChange={(value) => update('tax_rate', value)}
              error={fieldErrors.tax_rate}
            />
            <TextInput
              name="hsn_code"
              label="HSN code"
              value={form.hsn_code ?? ''}
              onChange={(value) => update('hsn_code', value)}
              error={fieldErrors.hsn_code}
              placeholder="8544"
            />
          </div>
        </div>

        <div className="card">
          <h3>Stock</h3>
          <div className="form-grid">
            {!isEdit ? (
              <TextInput
                name="opening_stock"
                label="Opening stock"
                type="number"
                min={0}
                value={String(form.opening_stock ?? 0)}
                onChange={(value) => update('opening_stock', Number(value) || 0)}
                error={fieldErrors.opening_stock}
                hint="Logged as an OPENING movement so the ledger stays complete."
              />
            ) : (
              <div className="form-group">
                <label>Current stock</label>
                <div className="panel" style={{ padding: 12 }}>
                  <strong style={{ fontSize: '1.4rem' }}>{existing.data?.current_stock ?? 0}</strong>{' '}
                  <span className="muted">{existing.data?.unit_display}</span>
                  <div className="helptext">
                    Change it from the product page (stock-take) or the stock log.
                  </div>
                </div>
              </div>
            )}
            <TextInput
              name="min_stock_alert"
              label="Minimum stock alert"
              type="number"
              min={0}
              value={String(form.min_stock_alert)}
              onChange={(value) => update('min_stock_alert', Number(value) || 0)}
              error={fieldErrors.min_stock_alert}
              hint="A low-stock warning appears at or below this quantity."
            />
            {isEdit ? (
              <div className="form-group">
                <label htmlFor="is_active">Status</label>
                <select
                  id="is_active"
                  value={form.is_active ? 'true' : 'false'}
                  onChange={(event) => update('is_active', event.target.value === 'true')}
                >
                  <option value="true">Active</option>
                  <option value="false">Archived</option>
                </select>
                <div className="helptext">Archived products stay on past challans and in the ledger.</div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="row row-end">
          <Link to={isEdit ? `/products/${id}` : '/products'} className="btn">
            Cancel
          </Link>
          <button type="submit" className="btn btn-accent" disabled={saving}>
            {saving ? 'Saving...' : isEdit ? 'Save changes' : 'Create product'}
          </button>
        </div>
      </form>
    </div>
  );
}
