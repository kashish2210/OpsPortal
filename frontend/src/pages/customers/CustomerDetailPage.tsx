import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { challans as challanApi, customers } from '../../api/endpoints';
import { IfAllowed } from '../../auth/guards';
import { useToast } from '../../components/Toast';
import {
  ChallanStatusBadge,
  CustomerStatusBadge,
  EmptyState,
  ErrorNote,
  Modal,
  PageHeader,
  SelectInput,
  Spinner,
  TextArea,
  TextInput,
} from '../../components/ui';
import { useApiResource, usePaginatedResource } from '../../hooks/useApiResource';
import { date, dateTime, money, relativeDays, today } from '../../utils/format';

const CHANNELS = [
  { value: 'CALL', label: 'Phone call' },
  { value: 'EMAIL', label: 'E-mail' },
  { value: 'WHATSAPP', label: 'WhatsApp' },
  { value: 'VISIT', label: 'Site visit' },
  { value: 'MEETING', label: 'Meeting' },
  { value: 'OTHER', label: 'Other' },
];

export function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const customerId = Number(id);
  const navigate = useNavigate();
  const toast = useToast();

  const [showFollowUp, setShowFollowUp] = useState(false);
  const [note, setNote] = useState('');
  const [channel, setChannel] = useState('CALL');
  const [nextDate, setNextDate] = useState('');
  const [saving, setSaving] = useState(false);
  const [followUpError, setFollowUpError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);

  const { data: customer, loading, error, reload } = useApiResource(
    (signal) => customers.get(customerId, signal),
    [customerId],
  );

  const followUps = usePaginatedResource(
    (signal) => customers.followUps(customerId, { page_size: 20 }, signal),
    [customerId, customer?.updated_at],
  );

  const customerChallans = usePaginatedResource(
    (signal) => challanApi.list({ customer: customerId, page_size: 10 }, signal),
    [customerId],
  );

  const submitFollowUp = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setFollowUpError(null);
    try {
      await customers.addFollowUp(customerId, {
        note,
        channel,
        next_follow_up_date: nextDate || null,
      });
      toast.success('Follow-up recorded.');
      setShowFollowUp(false);
      setNote('');
      setNextDate('');
      reload();
      followUps.reload();
    } catch (err) {
      setFollowUpError(err instanceof ApiError ? err.message : 'Could not save the follow-up.');
    } finally {
      setSaving(false);
    }
  };

  const archive = async () => {
    if (!window.confirm('Mark this customer inactive? Their challans and history are kept.')) return;
    setArchiving(true);
    try {
      await customers.archive(customerId);
      toast.info('Customer marked inactive.');
      reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not archive the customer.');
    } finally {
      setArchiving(false);
    }
  };

  if (loading && !customer) return <Spinner label="Loading customer..." />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!customer) return null;

  return (
    <div className="fade-in">
      <PageHeader
        title={customer.name}
        subtitle={
          <span className="row" style={{ gap: 8 }}>
            <span className="mono">{customer.code}</span>
            <CustomerStatusBadge status={customer.status} label={customer.status_display} />
            <span className="badge badge-muted">{customer.customer_type_display}</span>
          </span>
        }
        actions={
          <>
            <Link to="/customers" className="btn">
              Back
            </Link>
            <IfAllowed capability="customers.write">
              <button type="button" className="btn" onClick={() => setShowFollowUp(true)}>
                + Follow-up
              </button>
              <Link to={`/customers/${customer.id}/edit`} className="btn btn-accent">
                Edit
              </Link>
            </IfAllowed>
            <IfAllowed capability="challans.write">
              <Link to={`/challans/new?customer=${customer.id}`} className="btn">
                New challan
              </Link>
            </IfAllowed>
          </>
        }
      />

      {customer.is_follow_up_due ? (
        <div className="alert alert-warning">
          Follow-up was due {relativeDays(customer.follow_up_date)} ({date(customer.follow_up_date)}).
        </div>
      ) : null}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        <section className="card">
          <h3>Contact</h3>
          <table className="credential-table">
            <tbody>
              <tr>
                <td className="muted">Business</td>
                <td>{customer.business_name || '-'}</td>
              </tr>
              <tr>
                <td className="muted">Mobile</td>
                <td className="mono">{customer.mobile}</td>
              </tr>
              <tr>
                <td className="muted">E-mail</td>
                <td>{customer.email || '-'}</td>
              </tr>
              <tr>
                <td className="muted">GST</td>
                <td className="mono">{customer.gst_number || '-'}</td>
              </tr>
              <tr>
                <td className="muted">Address</td>
                <td>{customer.full_address || '-'}</td>
              </tr>
              <tr>
                <td className="muted">Credit limit</td>
                <td>{money(customer.credit_limit)}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="card">
          <h3>CRM</h3>
          <table className="credential-table">
            <tbody>
              <tr>
                <td className="muted">Next follow-up</td>
                <td>
                  {customer.follow_up_date
                    ? `${date(customer.follow_up_date)} (${relativeDays(customer.follow_up_date)})`
                    : 'Not scheduled'}
                </td>
              </tr>
              <tr>
                <td className="muted">Follow-ups</td>
                <td>{customer.follow_up_count}</td>
              </tr>
              <tr>
                <td className="muted">Challans</td>
                <td>{customer.challan_count}</td>
              </tr>
              <tr>
                <td className="muted">Added by</td>
                <td>{customer.created_by_name ?? '-'}</td>
              </tr>
              <tr>
                <td className="muted">Added on</td>
                <td>{dateTime(customer.created_at)}</td>
              </tr>
            </tbody>
          </table>

          {customer.notes ? (
            <>
              <hr className="hr-sketch" />
              <h4>Notes</h4>
              <p style={{ whiteSpace: 'pre-wrap' }}>{customer.notes}</p>
            </>
          ) : null}

          {customer.status !== 'INACTIVE' ? (
            <IfAllowed capability="customers.write">
              <hr className="hr-sketch" />
              <button type="button" className="btn btn-sm btn-danger" onClick={archive} disabled={archiving}>
                {archiving ? 'Archiving...' : 'Mark inactive'}
              </button>
            </IfAllowed>
          ) : null}
        </section>
      </div>

      <section className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h3>Follow-up history</h3>
          <IfAllowed capability="customers.write">
            <button type="button" className="btn btn-sm" onClick={() => setShowFollowUp(true)}>
              + Add note
            </button>
          </IfAllowed>
        </div>

        {followUps.loading && followUps.items.length === 0 ? <Spinner label="Loading notes..." /> : null}
        {!followUps.loading && followUps.items.length === 0 ? (
          <EmptyState title="No follow-ups recorded yet" hint="Log a call, visit or message here." />
        ) : null}

        {followUps.items.length > 0 ? (
          <ul className="activity-list" style={{ marginTop: 12 }}>
            {followUps.items.map((item) => (
              <li key={item.id} className="panel" style={{ padding: 14 }}>
                <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                  <span className="badge badge-info">{item.channel_display}</span>
                  <span className="muted" style={{ fontSize: '0.95rem' }}>
                    {dateTime(item.created_at)} &middot; {item.created_by_name ?? 'system'}
                  </span>
                </div>
                <p style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{item.note}</p>
                {item.next_follow_up_date ? (
                  <p className="muted" style={{ fontSize: '0.95rem', marginTop: 6 }}>
                    Next contact: {date(item.next_follow_up_date)}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h3>Recent challans</h3>
          <Link to={`/challans?customer=${customer.id}`} className="btn btn-sm">
            View all
          </Link>
        </div>

        {customerChallans.items.length === 0 ? (
          <EmptyState title="No challans raised for this customer yet" />
        ) : (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="sketch-table">
              <thead>
                <tr>
                  <th>Challan</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th className="num">Qty</th>
                  <th className="num">Value</th>
                </tr>
              </thead>
              <tbody>
                {customerChallans.items.map((challan) => (
                  <tr key={challan.id}>
                    <td>
                      <Link to={`/challans/${challan.id}`} className="mono">
                        {challan.challan_number}
                      </Link>
                    </td>
                    <td className="nowrap">{date(challan.challan_date)}</td>
                    <td>
                      <ChallanStatusBadge status={challan.status} label={challan.status_display} />
                    </td>
                    <td className="num">{challan.total_quantity}</td>
                    <td className="num">{money(challan.grand_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showFollowUp ? (
        <Modal
          title="Record a follow-up"
          onClose={() => setShowFollowUp(false)}
          footer={
            <>
              <button type="button" className="btn" onClick={() => setShowFollowUp(false)}>
                Cancel
              </button>
              <button type="submit" form="follow-up-form" className="btn btn-accent" disabled={saving}>
                {saving ? 'Saving...' : 'Save follow-up'}
              </button>
            </>
          }
        >
          <form id="follow-up-form" onSubmit={submitFollowUp}>
            {followUpError ? <div className="alert alert-error">{followUpError}</div> : null}
            <SelectInput
              name="channel"
              label="Channel"
              value={channel}
              onChange={setChannel}
              options={CHANNELS}
              required
            />
            <TextArea
              name="note"
              label="What happened?"
              value={note}
              onChange={setNote}
              rows={4}
              placeholder="Called to confirm the monthly requirement..."
            />
            <TextInput
              name="next_follow_up_date"
              label="Next follow-up date"
              type="date"
              value={nextDate}
              onChange={setNextDate}
              hint={`Optional. Cannot be before ${date(today())}.`}
            />
          </form>
        </Modal>
      ) : null}

      <div className="row" style={{ marginTop: 20 }}>
        <button type="button" className="btn btn-sm" onClick={() => navigate(-1)}>
          &larr; Back
        </button>
      </div>
    </div>
  );
}
