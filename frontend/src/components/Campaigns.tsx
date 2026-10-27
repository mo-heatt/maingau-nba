import {useEffect, useRef, useState} from 'react';
import {Check, LoaderCircle, Megaphone, Plus, Rocket, Trash2, X} from 'lucide-react';
import {useApi, request, eur, channel} from '../api';
import {STATIC_MODE} from '../staticApi';
import {Loading, Panel} from './ui';
import '../campaigns.css';

type Filter = 'value_tier' | 'tenure' | 'lines' | 'city' | 'product';
type Options = {offers: {id: string; name: string}[]; channels: {id: string; name: string}[]} & Record<Filter, string[]>;
type Audience = {total: number; targeted: number; contactable: number; control: number; expected_gain_eur: number; expected_yes: number; left_out: {reason: string; label: string; customers: number}[]};
type Tracking = {simulated: true; sent: number; seen: number; yes: number; control: number; control_yes: number; yes_rate: number | null; control_rate: number | null; uplift: number | null; value_won_eur: number};
type Spec = {name: string; offer: string; channel: string; starts: string; ends: string} & Record<Filter, string[]>;
export type Campaign = Spec & {id: number; status: 'draft' | 'running'; created_at: string; launched_at: string | null; audience: Audience; tracking: Tracking | null};

const FILTERS: [Filter, string][] = [['value_tier', 'Value'], ['tenure', 'Tenure'], ['lines', 'Products'], ['product', 'Holds tariff']];
const EMPTY: Spec = {name: '', offer: '', channel: 'newsletter_email', starts: '', ends: '', value_tier: [], tenure: [], lines: [], city: [], product: []};
const pct = (v: number | null) => v == null ? '—' : (v * 100).toFixed(1).replace('.', ',') + ' %';
const day = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', {day: 'numeric', month: 'short'});
// The API takes dates as null when empty.
const body = (s: Spec) => ({...s, starts: s.starts || null, ends: s.ends || null});

function target(c: Spec) {
  const parts = [...c.value_tier, ...c.tenure, ...c.lines, ...(c.product ?? []), ...c.city];
  return parts.length ? parts.join(' · ') : 'All customers';
}

// Who the campaign reaches, who may be contacted, and why everyone else is left out.
function AudienceBox({a, loading}: {a: Audience; loading?: boolean}) {
  return <div className={'cp-audience' + (loading ? ' loading' : '')}>
    <p className="cp-reach"><b>{a.contactable}</b> can be contacted <span>of {a.targeted} in the target group · {a.total} customers</span></p>
    <ul>{a.left_out.map(r => <li key={r.reason}><X size={13} aria-hidden="true" /><span>{r.label}</span><b>{r.customers}</b></li>)}</ul>
    <p className="cp-expect">Expected: about {Math.round(a.expected_yes)} yes · {eur(a.expected_gain_eur)} customer value</p>
  </div>;
}

export function NewCampaign({open, onClose, onCreated, prefill}: {open: boolean; onClose: () => void; onCreated: (c: Campaign) => void; prefill?: Partial<Spec>}) {
  const modal = useRef<HTMLDialogElement>(null);
  const {data: o} = useApi<Options>('/campaigns/options');
  const [spec, setSpec] = useState<Spec>(EMPTY), [preview, setPreview] = useState<{a: Audience | null; error: string; loading: boolean}>({a: null, error: '', loading: false}), [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {if (prefill) setSpec(s => ({...s, ...prefill})); modal.current?.showModal();}
    else {modal.current?.close();setSpec(EMPTY);setPreview({a: null, error: '', loading: false});setBusy(false)}
  }, [open]);
  useEffect(() => {if (o && !spec.offer) setSpec(s => ({...s, offer: o.offers[0].id}))}, [o, spec.offer]);

  // Recount the audience shortly after the form settles.
  const key = JSON.stringify({...spec, name: ''});
  useEffect(() => {
    if (!open || !spec.offer || STATIC_MODE) return;
    const ctl = new AbortController();
    setPreview(p => ({...p, loading: true, error: ''}));
    const timer = setTimeout(() => request<Audience>('/campaigns/preview', 'POST', body({...spec, name: spec.name || 'Preview'}), ctl.signal)
      .then(a => setPreview({a, error: '', loading: false}))
      .catch(e => {if (!ctl.signal.aborted) setPreview({a: null, error: (e as Error).message, loading: false})}), 350);
    return () => {clearTimeout(timer);ctl.abort()};
  }, [key, open]);

  const set = <K extends keyof Spec>(k: K, v: Spec[K]) => setSpec(s => ({...s, [k]: v}));
  const toggle = (f: Filter, v: string) => set(f, spec[f].includes(v) ? spec[f].filter(x => x !== v) : [...spec[f], v]);
  async function create() {
    setBusy(true);
    try {onCreated(await request<Campaign>('/campaigns', 'POST', body(spec)))}
    catch (e) {setPreview(p => ({...p, error: (e as Error).message}));setBusy(false)}
  }

  return <dialog ref={modal} className="developer-dialog campaign-dialog" aria-labelledby="campaign-title" onCancel={e => {e.preventDefault();if (!busy) onClose()}}>
    <div className="developer-dialog-header"><div><Megaphone size={21} /><div><h2 id="campaign-title">New campaign</h2><p>One offer, one channel, one target group.</p></div></div><button className="button icon-button" aria-label="Close new campaign" disabled={busy} onClick={onClose}><X size={19} /></button></div>
    <div className="developer-dialog-content">{STATIC_MODE ? <div className="notice">This is a read-only demo. Start the full app to create campaigns.</div> : !o ? <Loading /> : <>
      <div className="cp-form">
        <label className="cp-wide">Name<input value={spec.name} maxLength={80} placeholder="e.g. Autumn StromGarant" onChange={e => set('name', e.target.value)} /></label>
        <label>Offer<select value={spec.offer} onChange={e => set('offer', e.target.value)}>{o.offers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label>Channel<select value={spec.channel} onChange={e => set('channel', e.target.value)}>{o.channels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        {FILTERS.map(([f, label]) => <fieldset key={f} className="cp-wide"><legend>{label}</legend><div className="cp-chips">{o[f].map(v => <button key={v} type="button" aria-pressed={spec[f].includes(v)} className={spec[f].includes(v) ? 'on' : ''} onClick={() => toggle(f, v)}>{spec[f].includes(v) && <Check size={12} />}{v}</button>)}</div></fieldset>)}
        <label>City<select value={spec.city[0] || ''} onChange={e => set('city', e.target.value ? [e.target.value] : [])}><option value="">All cities</option>{o.city.map(c => <option key={c}>{c}</option>)}</select></label>
        <div className="cp-dates"><label>Starts<input type="date" value={spec.starts} onChange={e => set('starts', e.target.value)} /></label><label>Ends<input type="date" value={spec.ends} min={spec.starts || undefined} onChange={e => set('ends', e.target.value)} /></label></div>
      </div>
      {preview.error ? <div className="notice" role="alert">{preview.error}</div> : preview.a && <AudienceBox a={preview.a} loading={preview.loading} />}
      <div className="developer-key-actions"><button className="button primary" disabled={busy || !spec.name.trim() || !preview.a || !!preview.error} onClick={create}>{busy ? <LoaderCircle className="loading-spin" size={15} /> : <Plus size={15} />}Create campaign</button><button className="button" disabled={busy} onClick={onClose}>Cancel</button></div>
      <p className="developer-key-note">Saved as a draft. Nothing is sent: launching records the approval and starts simulated tracking. The 10 % control group is never contacted.</p>
    </>}</div>
  </dialog>;
}

function Funnel({t}: {t: Tracking}) {
  const steps: [string, number][] = [['Sent', t.sent], ['Seen', t.seen], ['Said yes', t.yes]];
  return <ol className="cp-funnel">{steps.map(([label, n]) => <li key={label}><span>{label}</span><div className="bar-track"><div style={{width: (t.sent ? n / t.sent * 100 : 0) + '%'}} /></div><b>{n}</b></li>)}</ol>;
}

export function CampaignsTab({revision, names, onNew, onChanged, notify}: {revision: number; names: Record<string, string>; onNew: () => void; onChanged: () => void; notify: (s: string) => void}) {
  const {data, error} = useApi<{items: Campaign[]}>('/campaigns', revision);
  const [busy, setBusy] = useState(0);
  async function act(c: Campaign, how: 'launch' | 'delete') {
    setBusy(c.id);
    try {
      if (how === 'launch') await request('/campaigns/' + c.id + '/launch', 'POST');
      else await request('/campaigns/' + c.id, 'DELETE');
      onChanged();
      notify(how === 'launch' ? `“${c.name}” is running. Nothing was sent; tracking results are simulated.` : `Draft “${c.name}” deleted.`);
    } catch (e) {notify((e as Error).message)} finally {setBusy(0)}
  }
  if (error) return <Loading error={error} />;
  if (!data) return <Loading />;
  if (!data.items.length) return <div className="cp-empty"><Megaphone size={26} /><h3>No campaigns yet</h3><p>Pick an offer, a channel and a target group. The engine's rules decide who may be contacted.</p><button className="button primary" onClick={onNew}><Plus size={15} />New campaign</button></div>;
  return <div className="cp-list">{data.items.map(c => {const t = c.tracking, a = c.audience;
    return <Panel key={c.id} title={c.name} subtitle={`${names[c.offer] || c.offer} · ${channel(c.channel)} · ${target(c)}${c.starts ? ' · ' + day(c.starts) + (c.ends ? ' – ' + day(c.ends) : '') : ''}`}
      action={<span className={'cp-status ' + c.status}>{c.status === 'running' ? 'Running' : 'Draft'}</span>}>
      <div className="cp-body">
        {t ? <>
          <div className="cp-track">
            <Funnel t={t} />
            <dl className="cp-kpis">
              <div><dt>Said yes</dt><dd>{pct(t.yes_rate)}</dd></div>
              <div><dt>Control group</dt><dd>{pct(t.control_rate)}<small>{t.control_yes} of {t.control} without contact</small></dd></div>
              <div><dt>Uplift</dt><dd className={t.uplift != null && t.uplift > 0 ? 'good' : ''}>{t.uplift == null ? '—' : (t.uplift > 0 ? '+' : '') + (t.uplift * 100).toFixed(1).replace('.', ',') + ' pts'}</dd></div>
              <div><dt>Customer value won</dt><dd>{eur(t.value_won_eur)}<small>expected {eur(a.expected_gain_eur)}</small></dd></div>
            </dl>
          </div>
          <p className="cp-sim">Simulated results: nothing is sent in this demo, so reactions are drawn from each customer's chance of yes.</p>
        </> : <>
          <AudienceBox a={a} />
          <div className="cp-actions"><button className="button primary" disabled={!!busy || !a.contactable} onClick={() => act(c, 'launch')}><Rocket size={14} />Approve & launch</button><button className="button" disabled={!!busy} onClick={() => act(c, 'delete')}><Trash2 size={14} />Delete</button></div>
        </>}
      </div>
    </Panel>;
  })}</div>;
}
