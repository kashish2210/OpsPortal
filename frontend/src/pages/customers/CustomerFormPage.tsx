import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { customers } from '../../api/endpoints';
import type { CustomerPayload, CustomerStatus, CustomerType } from '../../api/types';
import { useToast } from '../../components/Toast';
import { ErrorNote, PageHeader, SelectInput, Spinner, TextArea, TextInput } from '../../components/ui';
import { useApiResource } from '../../hooks/useApiResource';

const TYPE_OPTIONS = [
  { value: 'RETAIL', label: 'Retail' },
  { value: 'WHOLESALE', label: 'Wholesale' },
  { value: 'DISTRIBUTOR', label: 'Distributor' },
];

const STATUS_OPTIONS = [
  { value: 'LEAD', label: 'Lead' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'INACTIVE', label: 'Inactive' },
];

const EMPTY: CustomerPayload = {
  name: '',
  business_name: '',
  mobile: '',
  email: '',
  gst_number: '',
  customer_type: 'RETAIL',
  status: 'LEAD',
  address: '',
  city: '',
  state: '',
  pincode: '',
  credit_limit: '0',
  follow_up_date: '',
  notes: '',
};

export function CustomerFormPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const toast = useToast();

  const [form, setForm] = useState<CustomerPayload>(EMPTY);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const existing = useApiResource(
    (signal) => (isEdit ? customers.get(Number(id), signal) : Promise.resolve(null)),
    [id],
  );

  useEffect(() => {
    const record = existing.data;
    if (!record) return;
    setForm({
      name: record.name,
      business_name: record.business_name,
      mobile: record.mobile,
      email: record.email,
      gst_number: record.gst_number,
      customer_type: record.customer_type,
      status: record.status,
      address: record.address,
      city: record.city,
      state: record.state,
      pincode: record.pincode,
      credit_limit: record.credit_limit,
      follow_up_date: record.follow_up_date ?? '',
      notes: record.notes,
    });
  }, [existing.data]);

  const update = <K extends keyof CustomerPayload>(key: K, value: CustomerPayload[K]) => {
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

    const payload: CustomerPayload = {
      ...form,
      follow_up_date: form.follow_up_date ? form.follow_up_date : null,
    };

    try {
      const saved = isEdit
        ? await customers.update(Number(id), payload)
        : await customers.create(payload);
      toast.success(isEdit ? 'Customer updated.' : `${saved.name} added as ${saved.code}.`);
      navigate(`/customers/${saved.id}`, { replace: true });
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

  if (isEdit && existing.loading) return <Spinner label="Loading customer..." />;
  if (isEdit && existing.error) return <ErrorNote message={existing.error} onRetry={existing.reload} />;

  const requiresGst = form.customer_type === 'WHOLESALE' || form.customer_type === 'DISTRIBUTOR';

  return (
    <div className="fade-in">
      <PageHeader
        title={isEdit ? `Edit ${form.name || 'customer'}` : 'Add customer'}
        subtitle={isEdit ? existing.data?.code : 'A customer code is generated automatically.'}
        actions={
          <Link to={isEdit ? `/customers/${id}` : '/customers'} className="btn">
            Cancel
          </Link>
        }
      />

      <form onSubmit={handleSubmit}>
        {formError ? <div className="alert alert-error">{formError}</div> : null}

        <div className="card">
          <h3>Identity</h3>
          <div className="form-grid">
            <TextInput
              name="name"
              label="Customer name"
              value={form.name}
              onChange={(value) => update('name', value)}
              error={fieldErrors.name}
              required
              placeholder="Rajesh Kumar"
            />
            <TextInput
              name="business_name"
              label="Business name"
              value={form.business_name ?? ''}
              onChange={(value) => update('business_name', value)}
              error={fieldErrors.business_name}
              placeholder="Kumar General Store"
            />
            <SelectInput
              name="customer_type"
              label="Customer type"
              value={form.customer_type}
              onChange={(value) => update('customer_type', value as CustomerType)}
              options={TYPE_OPTIONS}
              error={fieldErrors.customer_type}
              required
            />
            <SelectInput
              name="status"
              label="Status"
              value={form.status}
              onChange={(value) => update('status', value as CustomerStatus)}
              options={STATUS_OPTIONS}
              error={fieldErrors.status}
              required
            />
          </div>
        </div>

        <div className="card">
          <h3>Contact</h3>
          <div className="form-grid">
            <TextInput
              name="mobile"
              label="Mobile number"
              type="tel"
              value={form.mobile}
              onChange={(value) => update('mobile', value)}
              error={fieldErrors.mobile}
              required
              placeholder="9820011223"
              hint="Must be unique - it is how the team looks customers up."
            />
            <TextInput
              name="email"
              label="E-mail"
              type="email"
              value={form.email ?? ''}
              onChange={(value) => update('email', value)}
              error={fieldErrors.email}
              placeholder="rajesh@kumarstore.in"
            />
            <TextInput
              name="gst_number"
              label="GST number"
              value={form.gst_number ?? ''}
              onChange={(value) => update('gst_number', value.toUpperCase())}
              error={fieldErrors.gst_number}
              required={requiresGst}
              placeholder="27AAPFU0939F1ZV"
              hint={
                requiresGst
                  ? 'Required for wholesale and distributor customers.'
                  : 'Optional for retail customers.'
              }
            />
            <TextInput
              name="credit_limit"
              label="Credit limit"
              type="number"
              min={0}
              step="0.01"
              value={form.credit_limit ?? '0'}
              onChange={(value) => update('credit_limit', value)}
              error={fieldErrors.credit_limit}
              hint="Informational only - challans are not blocked by it."
            />
          </div>
        </div>

        <div className="card">
          <h3>Address</h3>
          <div className="form-grid">
            <TextArea
              name="address"
              label="Street address"
              value={form.address ?? ''}
              onChange={(value) => update('address', value)}
              error={fieldErrors.address}
              className="span-2"
              placeholder="Shop 14, Linking Road"
            />
            <TextInput
              name="city"
              label="City"
              value={form.city ?? ''}
              onChange={(value) => update('city', value)}
              error={fieldErrors.city}
            />
            <TextInput
              name="state"
              label="State"
              value={form.state ?? ''}
              onChange={(value) => update('state', value)}
              error={fieldErrors.state}
            />
            <TextInput
              name="pincode"
              label="Pincode"
              value={form.pincode ?? ''}
              onChange={(value) => update('pincode', value)}
              error={fieldErrors.pincode}
            />
          </div>
        </div>

        <div className="card">
          <h3>CRM</h3>
          <div className="form-grid">
            <TextInput
              name="follow_up_date"
              label="Next follow-up"
              type="date"
              value={form.follow_up_date ?? ''}
              onChange={(value) => update('follow_up_date', value)}
              error={fieldErrors.follow_up_date}
              required={form.status === 'LEAD'}
              hint={form.status === 'LEAD' ? 'Required for new leads so they are not forgotten.' : undefined}
            />
            <TextArea
              name="notes"
              label="Notes"
              value={form.notes ?? ''}
              onChange={(value) => update('notes', value)}
              error={fieldErrors.notes}
              className="span-2"
              rows={4}
            />
          </div>
        </div>

        <div className="row row-end">
          <Link to={isEdit ? `/customers/${id}` : '/customers'} className="btn">
            Cancel
          </Link>
          <button type="submit" className="btn btn-accent" disabled={saving}>
            {saving ? 'Saving...' : isEdit ? 'Save changes' : 'Create customer'}
          </button>
        </div>
      </form>
    </div>
  );
}
