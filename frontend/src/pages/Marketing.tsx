import {useEffect, useMemo, useState} from 'react';
import {Activity, ArrowRight, ArrowUpRight, Check, CheckCheck, FileText, FlaskConical, LayoutDashboard, Megaphone, Plus, Recycle, RotateCcw, Save, Search, ShieldCheck, SlidersHorizontal, X} from 'lucide-react';
import {AISample} from '../components/AIDecision';
import {useApi, request, eur, channel} from '../api';
import type {Settings, Catalog, Marketing as MarketingData, QueueRow, Preview, Totals, Replay} from '../types';
import {Loading, Metric, PageTitle, Panel} from '../components/ui';
import {CampaignsTab, NewCampaign} from '../components/Campaigns';
import Lifecycle, {type CampaignPrefill} from '../components/Lifecycle';
import Recommendations from './Recommendations';
import '../marketing.css';

type Tab = 'monitor' | 'recommendations' | 'lifecycle' | 'campaigns' | 'approve' | 'steer' | 'content' | 'learn';
type Props = {revision: number; onSelect: (id: string) => void; onChanged: () => void; notify: (s: string) => void};

const TABS: [Tab, string, typeof Activity][] = [
  ['monitor', 'Monitor', Activity],
  ['recommendations', 'Recommendations', LayoutDashboard],
  ['lifecycle', 'Product lifecycle', Recycle],
  ['campaigns', 'Campaigns', Megaphone],
  ['approve', 'Approve', CheckCheck],
  ['steer', 'Steer', SlidersHorizontal],
  ['content', 'Content & tone', FileText],
  ['learn', 'Learn', FlaskConical],
];
const PAGE = 25;
const eur0 = (v: number) => new Intl.NumberFormat('de-DE', {style: 'currency', currency: 'EUR', maximumFractionDigits: 0}).format(v);
const signed = (v: number, f = eur0) => (v > 0 ? '+' : v < 0 ? '−' : '±') + f(Math.abs(v));
const pct = (v: number | null | undefined, d = 1) => v == null ? '—' : (v * 100).toFixed(d).replace('.', ',') + ' %';
const tone = (t: string) => t === 'du' ? 'Du' : 'Sie';
const STATUS: Record<string, string> = {pending: 'Awaiting approval', approved: 'Approved', rejected: 'Rejected', stale: 'Changed since review', held_out: 'Control group'};
// Settings without the revision, to tell whether the draft differs from what is saved.
const rules = (s: Settings | null) => s ? JSON.stringify({...s, version: 0}) : '';

function initialTab(): Tab {
  const t = new URLSearchParams(location.hash.split('?')[1] || '').get('tab');
  return TABS.some(([k]) => k === t) ? t as Tab : 'monitor';
}

export default function Marketing({revision, onSelect, onChanged, notify}: Props) {
  const {data: saved, error} = useApi<Settings>('/settings', revision);
  const {data: catalog} = useApi<Catalog>('/catalog');
  const {data: m, error: statsError} = useApi<MarketingData>('/marketing', revision);
  const [tab, setTab] = useState<Tab>(initialTab);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [preview, setPreview] = useState<{data: Preview | null; error: string; loading: boolean}>({data: null, error: '', loading: false});
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [prefill, setPrefill] = useState<CampaignPrefill | undefined>(undefined);
  useEffect(() => { if (saved) setDraft(saved); }, [saved]);
  // Links such as #marketing?tab=recommendations can arrive while this page is open.
  useEffect(() => { const fn = () => setTab(initialTab()); window.addEventListener('hashchange', fn); return () => window.removeEventListener('hashchange', fn); }, []);
  const dirty = !!draft && rules(draft) !== rules(saved);

  // What-if: once the draft settles, ask the server what the engine would decide under it.
  useEffect(() => {
    if (!dirty || !draft) { setPreview({data: null, error: '', loading: false}); return; }
    const ctl = new AbortController();
    setPreview(p => ({...p, loading: true, error: ''}));
    const timer = setTimeout(() => {
      request<Preview>('/marketing/preview', 'POST', draft, ctl.signal)
        .then(data => setPreview({data, error: '', loading: false}))
        .catch(e => { if (!ctl.signal.aborted) setPreview({data: null, error: (e as Error).message, loading: false}); });
    }, 450);
    return () => { clearTimeout(timer); ctl.abort(); };
  }, [rules(draft), dirty]);

  function go(t: Tab) {
    setTab(t);
    history.replaceState(null, '', '#marketing' + (t === 'monitor' ? '' : '?tab=' + t));
  }
  async function save() {
    if (!draft) return;
    setBusy(true);
    try { await request('/settings', 'PATCH', draft); onChanged(); notify('Rules applied. Every recommendation was recalculated on the server and the change is in the audit log.'); }
    catch (e) { notify((e as Error).message); }
    finally { setBusy(false); }
  }
  async function review(items: QueueRow[], status: 'approved' | 'rejected') {
    setBusy(true);
    let failed = 0;
    for (const c of items) {
      try { await request('/customers/' + c.id + '/reviews', 'POST', {decision_id: c.decision.id, status}); }
      catch { failed++; }
    }
    setBusy(false);
    onChanged();
    const done = items.length - failed;
    notify(`${done} ${status === 'approved' ? 'approved' : 'rejected'}${failed ? `, ${failed} skipped because the decision changed` : ''}. Nothing was sent: delivery stays off until a person releases it.`);
  }

  if (error || statsError) return <Loading error={error || statsError} />;
  if (!m || !catalog || !draft) return <Loading />;
  const names: Record<string, string> = Object.fromEntries(catalog.products.map(p => [p.product_id, p.product_name]));

  return <div className="mk">
    <PageTitle eyebrow="Marketing orchestration" title="Steer the engine. Approve what goes out.">
      <div className="mk-title-actions"><span className="pill">Rules revision {saved?.version} · nothing is sent automatically</span><button className="button primary" onClick={() => setCreating(true)}><Plus size={15} />New campaign</button></div>
    </PageTitle>
    <NewCampaign open={creating} prefill={prefill} onClose={() => { setCreating(false); setPrefill(undefined); }} onCreated={c => { setCreating(false); setPrefill(undefined); go('campaigns'); onChanged(); notify(`Campaign “${c.name}” saved as a draft. Approve & launch it when ready.`); }} />
    <p className="page-intro">The engine proposes one next best action per customer, ranked by expected gain in customer lifetime value. Marketing sets the boundaries, approves offers, texts and tone, and watches whether contacts really cause the result.</p>

    <div className="metrics">
      <Metric label="Expected CLV gain, ready to approve" value={eur0(m.contactable_gain_eur)} hint={`${eur0(m.approved_gain_eur)} approved so far`} />
      <Metric label="Actions awaiting approval" value={m.funnel.pending + m.funnel.stale} hint={`${m.funnel.approved} approved · ${m.funnel.rejected} rejected`} />
      <Metric label="Left alone on purpose" value={m.no_contact} hint="no worthwhile offer, limit reached or a person decides" />
      <Metric label="Held out to measure" value={m.held_out} hint="stable 10 % control group, never contacted" />
    </div>

    <nav className="customer-detail-tabs mk-tabs" aria-label="Marketing sections">
      {TABS.map(([k, label, Icon]) => <button key={k} className={tab === k ? 'active' : ''} aria-current={tab === k ? 'page' : undefined} onClick={() => go(k)}>
        <Icon size={15} />{label}
        {k === 'approve' && m.funnel.pending + m.funnel.stale > 0 && <span>{m.funnel.pending + m.funnel.stale}</span>}
        {(k === 'steer' || k === 'content') && dirty && <i className="mk-dot" aria-label="unsaved changes" />}
      </button>)}
    </nav>

    {tab === 'monitor' && <Monitor m={m} revision={revision} onSelect={onSelect} onGo={go} />}
    {tab === 'recommendations' && <Recommendations revision={revision} onSelect={onSelect} embedded />}
    {tab === 'lifecycle' && <Lifecycle revision={revision} names={names} onNewCampaign={p => { setPrefill(p); setCreating(true); }} />}
    {tab === 'campaigns' && <CampaignsTab revision={revision} names={names} onNew={() => setCreating(true)} onChanged={onChanged} notify={notify} />}
    {tab === 'approve' && <Approve m={m} names={names} busy={busy} onSelect={onSelect} onReview={review} />}
    {tab === 'steer' && <Steer m={m} catalog={catalog} draft={draft} setDraft={setDraft} preview={preview} dirty={dirty} />}
    {tab === 'content' && <Content m={m} catalog={catalog} draft={draft} setDraft={setDraft} onSelect={onSelect} />}
    {tab === 'learn' && <Learn m={m} names={names} />}

    {dirty && <div className="mk-changes" role="region" aria-label="Unsaved rule changes">
      <div>
        <b>Unsaved rule changes</b>
        <span>{preview.loading ? 'Recalculating 750 customers…' : preview.error ? preview.error : preview.data ? <>Expected gain {eur0(preview.data.before.expected_gain_eur)} → <b>{eur0(preview.data.after.expected_gain_eur)}</b> ({signed(preview.data.after.expected_gain_eur - preview.data.before.expected_gain_eur)}) · actions {preview.data.before.offers + preview.data.before.service_fixes} → {preview.data.after.offers + preview.data.after.service_fixes}</> : null}</span>
      </div>
      <div className="mk-changes-actions">
        {tab !== 'steer' && <button className="button" onClick={() => go('steer')}>See impact</button>}
        <button className="button" disabled={busy} onClick={() => setDraft(saved)}><RotateCcw size={14} />Discard</button>
        <button className="button primary" disabled={busy} onClick={save}><Save size={14} />Apply rules</button>
      </div>
    </div>}
  </div>;
}

/* ---------- Monitor: where the value is, who it reaches, who the rules protect ---------- */

function Bars({rows, label, max}: {rows: {key: string; customers: number; expected_gain_eur: number}[]; label: (k: string) => string; max?: number}) {
  const top = max ?? Math.max(1, ...rows.map(r => r.expected_gain_eur));
  return <div className="mk-bars">{rows.map(r => <div className="mk-bar" key={r.key}>
    <span>{label(r.key)}</span>
    <div className="bar-track"><div style={{width: Math.max(1, r.expected_gain_eur / top * 100) + '%'}} /></div>
    <b>{eur0(r.expected_gain_eur)}</b>
    <small>{r.customers} customer{r.customers === 1 ? '' : 's'}</small>
  </div>)}</div>;
}

function Monitor({m, revision, onSelect, onGo}: {m: MarketingData; revision: number; onSelect: (id: string) => void; onGo: (t: Tab) => void}) {
  const cuts = Object.keys(m.segments);
  const [cut, setCut] = useState(cuts[0]);
  const {data: replay} = useApi<Replay>('/replay', revision);
  const segs = m.segments[cut] || [];
  const changed = (replay?.changes || []).filter(c => c.changed);
  return <>
    <div className="mk-grid">
      <Panel title="Top next best actions" subtitle="Expected CLV gain per action across all customers, incl. the control group">
        <Bars rows={m.top_actions.map(a => ({key: a.name, customers: a.customers, expected_gain_eur: a.expected_gain_eur}))} label={k => k} />
      </Panel>
      <Panel title="Where the engine reaches people" subtitle="Chosen channel and form of address for every proposed action">
        <h3 className="mk-sub">Channel</h3>
        <Bars rows={m.channel_mix} label={channel} />
        <h3 className="mk-sub">Tone</h3>
        <Bars rows={m.tone_mix} label={tone} />
      </Panel>
    </div>

    <Panel title="Segments" subtitle="Same engine, different customers: how many get an action, what they get and what it is worth"
      action={<div className="segmented" role="group" aria-label="Segment by">{cuts.map(c => <button key={c} className={c === cut ? 'active' : ''} aria-pressed={c === cut} onClick={() => setCut(c)}>{c}</button>)}</div>}>
      <div className="table-wrap"><table className="mk-table">
        <thead><tr><th>Segment</th><th className="right">Customers</th><th>Reached with an action</th><th className="right">Service first</th><th className="right">Avg. CLV</th><th className="right">Expected gain</th><th>Most common action</th></tr></thead>
        <tbody>{segs.map(s => <tr key={s.segment}>
          <td><b>{s.segment}</b></td>
          <td className="right">{s.customers}</td>
          <td><div className="mk-share"><div className="bar-track"><div style={{width: s.actions / s.customers * 100 + '%'}} /></div><span>{s.actions} · {pct(s.actions / s.customers, 0)}</span></div></td>
          <td className="right">{s.service_fixes}</td>
          <td className="right">{eur0(s.avg_clv_eur)}</td>
          <td className="right amount">{eur0(s.expected_gain_eur)}</td>
          <td>{s.top_action || '—'}<small>{s.top_action_customers} customers</small></td>
        </tr>)}</tbody>
      </table></div>
    </Panel>

    <div className="mk-grid">
      <Panel title="Left alone on purpose" subtitle={`${m.no_contact} customers get no contact this run, and why`}>
        <ul className="mk-list">{m.left_alone.map(r => <li key={r.key}><span>{r.label}</span><b>{r.customers}</b></li>)}</ul>
      </Panel>
      <Panel title="Protected by hard rules" subtitle="Customers for whom at least one offer was blocked. A customer can appear in several rows.">
        <ul className="mk-list">{m.protected.map(r => <li key={r.key}><span><ShieldCheck size={14} />{r.label}</span><b>{r.customers}</b></li>)}</ul>
        <p className="mk-note">Consent is checked per channel, exclusions beat offers, and payment data is used only to exclude. Our engine proposes zero actions that break these rules.</p>
      </Panel>
    </div>

    <Panel title="Today’s event stream" subtitle={replay ? `${replay.source_events} events from 1 October, ${replay.duplicates_skipped} duplicates skipped. ${replay.changed} changed a customer’s next best action.` : 'Replaying the event stream…'}>
      {replay && <ul className="mk-events">{changed.slice(0, 8).map(c => <li key={c.event_id}>
        <span className="d">{c.occurred_at.slice(11, 16)}</span>
        <button className="link" onClick={() => onSelect(c.customer_id)}>{c.customer_id}</button>
        <span className="note">{c.note}</span>
        <span className="mk-change"><s>{c.before}</s><ArrowRight size={12} /><b>{c.after}</b></span>
      </li>)}{!changed.length && <li className="muted">No decision changed today.</li>}</ul>}
    </Panel>

    <div className="mk-next">
      <button onClick={() => onGo('approve')}><b>Approve the queue <ArrowRight size={14} /></b><span>{m.funnel.pending + m.funnel.stale} actions wait for a marketer</span></button>
      <button onClick={() => onGo('steer')}><b>Change the rules <ArrowRight size={14} /></b><span>Contact limit, priorities, channels, with a live impact preview</span></button>
      <button onClick={() => onGo('learn')}><b>Check what works <ArrowRight size={14} /></b><span>Uplift against the control group, per offer</span></button>
    </div>
  </>;
}

/* ---------- Approve: the queue, with filters and bulk review ---------- */

function Approve({m, names, busy, onSelect, onReview}: {m: MarketingData; names: Record<string, string>; busy: boolean; onSelect: (id: string) => void; onReview: (items: QueueRow[], status: 'approved' | 'rejected') => Promise<void>}) {
  const [f, setF] = useState({q: '', action: '', channel: '', tone: '', tier: '', status: 'open'});
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<string | null>(null);
  const [shown, setShown] = useState(PAGE);
  const options = useMemo(() => {
    const u = (fn: (r: QueueRow) => string) => [...new Set(m.queue.map(fn))].sort();
    return {action: u(r => r.decision.product_id || ''), channel: u(r => r.decision.channel || ''), tier: u(r => r.segment.tier)};
  }, [m.queue]);
  const rows = m.queue.filter(r => {
    const d = r.decision;
    return (r.id + ' ' + r.city).toLowerCase().includes(f.q.toLowerCase())
      && (!f.action || d.product_id === f.action) && (!f.channel || d.channel === f.channel) && (!f.tone || d.tone === f.tone) && (!f.tier || r.segment.tier === f.tier)
      && (f.status === 'all' || (f.status === 'open' ? ['pending', 'stale'].includes(d.status) : d.status === f.status));
  });
  const set = (k: keyof typeof f) => (e: {target: {value: string}}) => { setF({...f, [k]: e.target.value}); setShown(PAGE); setPicked(new Set()); };
  const visible = rows.slice(0, shown);
  const reviewable = (r: QueueRow) => r.decision.status !== 'approved';
  const chosen = rows.filter(r => picked.has(r.id));
  const gain = chosen.reduce((a, r) => a + r.decision.expected_gain_eur, 0);
  const allPicked = visible.length > 0 && visible.filter(reviewable).every(r => picked.has(r.id));
  const toggle = (id: string) => setPicked(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  async function run(items: QueueRow[], status: 'approved' | 'rejected') { await onReview(items, status); setPicked(new Set()); }

  return <Panel title="Approval queue" subtitle={`${rows.length} of ${m.queue.length} proposed actions · sorted by expected CLV gain · ${m.held_out} control-group customers are held out and never shown here`}>
    <div className="directory-filter-panel mk-filters">
      <label className="search"><Search size={15} /><input aria-label="Search customer or city" placeholder="Customer or city" value={f.q} onChange={set('q')} /></label>
      <label>Action<select value={f.action} onChange={set('action')}><option value="">All actions</option>{options.action.map(a => <option key={a} value={a}>{names[a] || a}</option>)}</select></label>
      <label>Channel<select value={f.channel} onChange={set('channel')}><option value="">All channels</option>{options.channel.map(c => <option key={c} value={c}>{channel(c)}</option>)}</select></label>
      <label>Tone<select value={f.tone} onChange={set('tone')}><option value="">Du and Sie</option><option value="du">Du</option><option value="sie">Sie</option></select></label>
      <label>Value tier<select value={f.tier} onChange={set('tier')}><option value="">All tiers</option>{options.tier.map(t => <option key={t}>{t}</option>)}</select></label>
      <label>Status<select value={f.status} onChange={set('status')}><option value="open">Awaiting approval</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="all">All</option></select></label>
    </div>
    <div className="mk-bulk">
      <span>{chosen.length ? <><b>{chosen.length} selected</b> · {eur0(gain)} expected gain</> : 'Select actions to review them together, or open one to read the text.'}</span>
      <button className="button" disabled={busy || !chosen.length} onClick={() => run(chosen, 'rejected')}><X size={14} />Reject</button>
      <button className="button primary" disabled={busy || !chosen.length} onClick={() => run(chosen, 'approved')}><Check size={14} />Approve {chosen.length || ''}</button>
    </div>
    <div className="table-wrap"><table className="mk-table mk-queue">
      <thead><tr>
        <th><input type="checkbox" aria-label="Select all visible" checked={allPicked} onChange={() => setPicked(allPicked ? new Set() : new Set([...picked, ...visible.filter(reviewable).map(r => r.id)]))} /></th>
        <th>Customer</th><th>Next best action and why</th><th>Channel · tone</th><th className="right">p(accept)</th><th className="right">Expected gain</th><th>Status</th><th />
      </tr></thead>
      <tbody>{visible.map(r => {
        const d = r.decision;
        return [<tr key={r.id} className={picked.has(r.id) ? 'picked' : ''}>
          <td><input type="checkbox" aria-label={'Select ' + r.id} disabled={!reviewable(r)} checked={picked.has(r.id)} onChange={() => toggle(r.id)} /></td>
          <td><button className="link" onClick={() => onSelect(r.id)}>{r.id}<ArrowUpRight size={13} /></button><small>{r.city} · {r.segment.tier.split(' (')[0]}</small></td>
          <td className="mk-why"><b>{d.name}</b>{d.overridden && <em>changed by marketing</em>}<small>{d.reason}</small></td>
          <td>{channel(d.channel)}<small>{tone(d.tone)}</small></td>
          <td className="right">{pct(d.p_accept)}</td>
          <td className="right amount">+{eur(d.expected_gain_eur)}</td>
          <td><span className={'mk-status ' + d.status}>{STATUS[d.status] || d.status}</span></td>
          <td className="right"><button className="button small" aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)}>{open === r.id ? 'Close' : 'Text'}</button></td>
        </tr>,
        open === r.id && <tr key={r.id + '-msg'} className="mk-msg-row"><td /><td colSpan={7}>
          {d.message ? <div className="mk-msg"><div className="eyebrow">{d.action === 'service' ? 'Service task note' : 'Approved template'} · {tone(d.message.tone)} · German</div><b>{d.message.subject}</b><p>{d.message.body}</p></div> : <p className="muted">No text for this action.</p>}
          <ul className="mk-log">{d.log.map((l, i) => <li key={i}>{l}</li>)}</ul>
          {reviewable(r) && <div className="mk-msg-actions"><button className="button" disabled={busy} onClick={() => run([r], 'rejected')}><X size={14} />Reject</button><button className="button primary" disabled={busy} onClick={() => run([r], 'approved')}><Check size={14} />{d.action === 'service' ? 'Create service task' : 'Approve'}</button></div>}
        </td></tr>];
      })}</tbody>
    </table>{!rows.length && <div className="empty">No actions match these filters.</div>}</div>
    {rows.length > shown && <div className="show-more"><button className="button" onClick={() => setShown(n => n + PAGE)}>Show {Math.min(PAGE, rows.length - shown)} more</button></div>}
  </Panel>;
}

/* ---------- Steer: rules with a live what-if ---------- */

function Steer({m, catalog, draft, setDraft, preview, dirty}: {m: MarketingData; catalog: Catalog; draft: Settings; setDraft: (s: Settings) => void; preview: {data: Preview | null; error: string; loading: boolean}; dirty: boolean}) {
  const offers = catalog.products.filter(p => p.product_id !== 'P-EN-04');
  const live = Object.fromEntries(m.top_actions.map(a => [a.product_id, a]));
  const used = Object.fromEntries(m.channel_mix.map(c => [c.key, c.customers]));
  const toggle = (list: string[], id: string, on: boolean) => on ? list.filter(v => v !== id) : [...list, id];
  return <div className="mk-steer">
    <div>
      <Panel title="Limits" subtitle="Applied to every customer before ranking">
        <div className="mk-form">
          <label><span>Marketing contacts per customer in 30 days <b>{draft.contact_cap_30d}</b></span><input type="range" min="1" max="6" value={draft.contact_cap_30d} onChange={e => setDraft({...draft, contact_cap_30d: +e.target.value})} /><small>More contacts cause fatigue. Customers at the limit wait.</small></label>
          <label><span>Minimum expected gain per action</span><div className="mk-input"><input type="number" min="0" step="1" value={draft.min_dclv_eur} onChange={e => setDraft({...draft, min_dclv_eur: Math.max(0, +e.target.value)})} /><i>€</i></div><small>Actions worth less are dropped: no contact without value.</small></label>
          <fieldset><legend>Form of address</legend>
            <div className="segmented">{([['mirror', 'Mirror the customer'], ['sie', 'Always Sie']] as const).map(([v, l]) => <button key={v} className={draft.tone_mode === v ? 'active' : ''} aria-pressed={draft.tone_mode === v} onClick={() => setDraft({...draft, tone_mode: v})}>{l}</button>)}</div>
            <small>Mirroring needs profiling consent; without it the engine always uses Sie.</small>
          </fieldset>
        </div>
      </Panel>
      <Panel title="Offers and priorities" subtitle="Turn an offer off, or weight it in the ranking. Shown euro values stay the unweighted estimates.">
        <div className="table-wrap"><table className="mk-table mk-offers">
          <thead><tr><th>Offer</th><th className="right">Now proposed</th><th>Priority</th><th className="right">Active</th></tr></thead>
          <tbody>{offers.map(p => {
            const on = !draft.offers_off.includes(p.product_id), a = live[p.product_id];
            return <tr key={p.product_id} className={on ? '' : 'off'}>
              <td><b>{p.product_name}</b><small>{p.business_line.replace('_', ' ')} · {p.action_type}</small></td>
              <td className="right">{a ? <>{a.customers}<small>{eur0(a.expected_gain_eur)}</small></> : <span className="muted">—</span>}</td>
              <td>{p.action_type === 'service' ? <small>Always first during a service case</small> : <div className="segmented">{(['low', 'normal', 'high'] as const).map(v => <button key={v} disabled={!on} className={(draft.priorities[p.product_id] || 'normal') === v ? 'active' : ''} aria-pressed={(draft.priorities[p.product_id] || 'normal') === v} onClick={() => setDraft({...draft, priorities: {...draft.priorities, [p.product_id]: v}})}>{v[0].toUpperCase() + v.slice(1)}</button>)}</div>}</td>
              <td className="right"><Switch on={on} label={p.product_name} onChange={v => setDraft({...draft, offers_off: toggle(draft.offers_off, p.product_id, v)})} /></td>
            </tr>;
          })}</tbody>
        </table></div>
      </Panel>
      <Panel title="Channels" subtitle="Consent is always checked per customer; here marketing can switch a channel off for everyone">
        <ul className="mk-list mk-channels">{catalog.channels.map(c => { const on = !draft.channels_off.includes(c); return <li key={c} className={on ? '' : 'off'}><span>{channel(c)}<small>{used[c] ? `${used[c]} actions now` : 'not chosen now'}</small></span><Switch on={on} label={channel(c)} onChange={v => setDraft({...draft, channels_off: toggle(draft.channels_off, c, v)})} /></li>; })}</ul>
      </Panel>
    </div>
    <aside className="panel mk-impact" aria-live="polite">
      <div className="panel-heading"><div><h2>Impact preview</h2><p>{dirty ? 'What the engine would decide under your draft, for all 750 customers' : 'Change a rule to see what it does before you apply it'}</p></div></div>
      {!dirty ? <p className="mk-impact-empty">The engine re-scores every customer with your draft rules. Nothing is saved until you apply.</p>
        : preview.error ? <p className="empty error">{preview.error}</p>
        : !preview.data ? <p className="mk-impact-empty">Recalculating…</p>
        : <Impact p={preview.data} loading={preview.loading} />}
    </aside>
  </div>;
}

function Switch({on, label, onChange}: {on: boolean; label: string; onChange: (on: boolean) => void}) {
  return <button role="switch" aria-checked={on} aria-label={label} className={'mk-switch' + (on ? ' on' : '')} onClick={() => onChange(!on)}><span /></button>;
}

function Impact({p, loading}: {p: Preview; loading: boolean}) {
  const {before: b, after: a} = p;
  const row = (label: string, k: keyof Totals, money = false) => {
    const x = b[k] as number, y = a[k] as number;
    return <li key={k}><span>{label}</span><span>{money ? eur0(x) : x}</span><b>{money ? eur0(y) : y}</b><em className={y > x ? 'up' : y < x ? 'down' : ''}>{y === x ? '±0' : money ? signed(y - x) : (y > x ? '+' : '−') + Math.abs(y - x)}</em></li>;
  };
  const acts = [...new Set([...Object.keys(b.by_action), ...Object.keys(a.by_action)])]
    .map(k => ({k, x: b.by_action[k] || 0, y: a.by_action[k] || 0})).filter(r => r.x !== r.y).sort((r, s) => Math.abs(s.y - s.x) - Math.abs(r.y - r.x));
  return <div className={loading ? 'mk-impact-body stale' : 'mk-impact-body'}>
    <ul className="mk-delta"><li className="head"><span /><span>Now</span><b>Draft</b><em>Change</em></li>
      {row('Expected CLV gain', 'expected_gain_eur', true)}
      {row('Offers', 'offers')}
      {row('Service fixes', 'service_fixes')}
      {row('Waiting (contact limit)', 'wait')}
      {row('No contact', 'no_contact')}
    </ul>
    <h3 className="mk-sub">Actions that move</h3>
    {acts.length ? <ul className="mk-delta small">{acts.slice(0, 8).map(r => <li key={r.k}><span>{r.k}</span><span>{r.x}</span><b>{r.y}</b><em className={r.y > r.x ? 'up' : 'down'}>{(r.y > r.x ? '+' : '−') + Math.abs(r.y - r.x)}</em></li>)}</ul> : <p className="mk-note">No customer switches to a different action.</p>}
  </div>;
}

/* ---------- Content & tone: approve the German texts per offer and form of address ---------- */

function Content({m, catalog, draft, setDraft, onSelect}: {m: MarketingData; catalog: Catalog; draft: Settings; setDraft: (s: Settings) => void; onSelect: (id: string) => void}) {
  const names = Object.fromEntries(catalog.products.map(p => [p.product_id, p.product_name]));
  const ids = Object.keys(catalog.templates).filter(id => id !== 'P-SV-01')
    .sort((x, y) => sum(m.template_use[y]) - sum(m.template_use[x]));
  return <>
    <Panel title="Approved texts" subtitle="Every customer message is built from one of these German templates. Withdraw a text and the engine stops proposing that offer in that tone.">
      <div className="mk-templates">{ids.map(id => <div className="mk-template" key={id}>
        <header><b>{names[id] || id}</b><small>{sum(m.template_use[id])} live actions use this offer</small></header>
        <div className="mk-tones">{Object.entries(catalog.templates[id]).map(([t, [subject, body]]) => {
          const on = draft.content_approvals[id]?.[t] !== false, n = m.template_use[id]?.[t] || 0;
          return <article key={t} className={on ? '' : 'off'}>
            <div className="mk-tone-head"><span className="mk-tone">{tone(t)}</span><small>{n} customer{n === 1 ? '' : 's'}</small><Switch on={on} label={`${names[id] || id}, ${tone(t)} text approved`} onChange={v => setDraft({...draft, content_approvals: {...draft.content_approvals, [id]: {...draft.content_approvals[id], [t]: v}}})} /></div>
            <b>{subject}</b>
            <p>{body}</p>
          </article>;
        })}</div>
      </div>)}</div>
    </Panel>
    <Panel title="Content guardrails" subtitle="Checked for every text before it is approved">
      <ul className="ov-rules">{['No personalised prices', 'No fake urgency or pressure', 'No targeting of customers in hardship', 'Du only when the customer writes informally and agreed to profiling', 'Customer texts in German', 'AI may only rephrase inside an approved template'].map(r => <li key={r}><Check size={14} />{r}</li>)}</ul>
    </Panel>
    <AISample onSelect={onSelect} />
  </>;
}
const sum = (o?: Record<string, number>) => Object.values(o || {}).reduce((a, b) => a + b, 0);

/* ---------- Learn: does a contact cause the result? ---------- */

function Learn({m, names}: {m: MarketingData; names: Record<string, string>}) {
  const o = m.acceptance.overall;
  const rows = [...m.acceptance.uplift].sort((a, b) => (b.uplift ?? -1) - (a.uplift ?? -1));
  const span = Math.max(0.01, ...rows.map(r => Math.abs(r.uplift ?? 0)));
  return <>
    <div className="metrics three">
      <Metric label="Bought after a contact" value={pct(o.treated)} hint={`${o.treated_n.toLocaleString('en-GB')} contacted customers, 14 days`} />
      <Metric label="Bought without a contact" value={pct(o.control)} hint={`${o.control_n} control-group customers`} />
      <Metric label="Uplift caused by contacting" value={(o.treated - o.control >= 0 ? '+' : '') + ((o.treated - o.control) * 100).toFixed(1).replace('.', ',') + ' pp'} hint="the part that would not have happened anyway" />
    </div>
    <Panel title="Uplift per offer" subtitle="Last season’s actions, June to September. Treated minus control conversion within 14 days.">
      <div className="table-wrap"><table className="mk-table">
        <thead><tr><th>Offer</th><th className="right">Contacted</th><th className="right">Control</th><th>Uplift</th><th>Read</th></tr></thead>
        <tbody>{rows.map(r => {
          const thin = r.control_n < 30, u = r.uplift ?? 0;
          return <tr key={r.offer}>
            <td><b>{names[r.offer] || r.offer}</b></td>
            <td className="right">{pct(r.treated_rate)}<small>n = {r.treated_n}</small></td>
            <td className="right">{pct(r.control_rate)}<small>n = {r.control_n}</small></td>
            <td><div className="mk-diverge"><div className={u < 0 ? 'neg' : 'pos'} style={{width: Math.abs(u) / span * 50 + '%'}} /></div><span className={u < 0 ? 'mk-down' : 'mk-up'}>{r.uplift == null ? '—' : (u >= 0 ? '+' : '') + (u * 100).toFixed(1).replace('.', ',') + ' pp'}</span></td>
            <td><small>{u < 0 ? 'Contact may hurt: review before scaling' : u === 0 ? 'No effect measured' : thin ? 'Positive, control group still small' : 'Works: offer more often'}</small></td>
          </tr>;
        })}</tbody>
      </table></div>
    </Panel>
    <Panel title="How the engine learns" subtitle="Concept, built on the data the engine already logs">
      <div className="ov-steps mk-loop">{[
        ['Hold out', '1 in 10 customers is assigned to a stable control group by a hash of the customer_id and never contacted.'],
        ['Log', 'Every decision is stored with inputs, rules, scores, chosen action, approval and response.'],
        ['Compare', 'After 14 days, conversion of contacted vs. held-out customers per offer and channel gives the uplift.'],
        ['Update', 'Uplift, not raw conversion, replaces p(accept). Offers that do not cause sales sink in the ranking.'],
      ].map(([t, x], i) => <div key={t}><span>{i + 1}</span><h3>{t}</h3><p>{x}</p></div>)}</div>
    </Panel>
  </>;
}
