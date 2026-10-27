import {useEffect, useRef, useState} from 'react';
import {ArrowLeft, ArrowRight, Check, Clock3, Lightbulb, LoaderCircle, Megaphone, Plus, Repeat2, Rocket, Sparkles, Trash2, TriangleAlert, ThumbsUp, X} from 'lucide-react';
import {useApi, request, eur} from '../api';
import {STATIC_MODE} from '../staticApi';
import {Loading, Panel} from './ui';
import '../campaigns.css';

type Filter = 'value_tier' | 'tenure' | 'lines' | 'city' | 'product';
type Options = {offers: {id: string; name: string; description: string}[]; channels: {id: string; name: string}[]} & Record<Filter, string[]>;
type Message = {language: string; subject: string; body: string};
type Segment = {key: string; need: string; channel: string; channel_label: string; customers: number; expected_yes: number; expected_gain_eur: number; gain_per_contact_eur: number; recommended: boolean; included: boolean; tones: Record<string, number>; languages: Record<string, number>; best_time: string; examples: {id: string; reason: string; tone: string; time: string}[]; messages: Record<string, Message>};
type Audience = {total: number; targeted: number; eligible: number; contactable: number; control: number; expected_gain_eur: number; expected_yes: number; left_out: {reason: string; label: string; customers: number}[]; segments: Segment[]};
type Advice = {source: 'ai' | 'rules'; summary: string; note?: string; segments: {segment: string; include: boolean; priority: 'high' | 'normal' | 'low'; angle: string}[]; risks: string[]; ideas: string[]};
type Result = {sent: number; seen: number; yes: number; yes_rate: number | null; control: number; control_yes: number; control_rate: number | null; uplift: number | null; value_won_eur: number; expected_gain_eur: number};
type Breakdown = Result & {key: string; label: string};
type Tracking = Result & {simulated: true; days: number; timeline: {day: number; sent: number; yes: number; expected_yes: number}[]; segments: Breakdown[]; channels: Breakdown[]};
type Insight = {kind: 'good' | 'warn' | 'idea'; title: string; text: string; drop?: string};
type Spec = {name: string; goal: string; offer: string; channel: string; starts: string; ends: string; segments: string[]} & Record<Filter, string[]>;
export type Campaign = Spec & {id: number; status: 'draft' | 'running'; created_at: string; launched_at: string | null; follows?: number; audience: Audience; tracking: Tracking | null; insights: Insight[]};

const FILTERS: [Filter, string][] = [['value_tier', 'Value'], ['tenure', 'Tenure'], ['lines', 'Products'], ['product', 'Holds tariff']];
const STEPS = ['Brief', 'Audience', 'Messages', 'Review'];
const EMPTY: Spec = {name: '', goal: '', offer: '', channel: '', starts: '', ends: '', segments: [], value_tier: [], tenure: [], lines: [], city: [], product: []};
const pct = (v: number | null) => v == null ? '—' : (v * 100).toFixed(1).replace('.', ',') + ' %';
const pts = (v: number | null) => v == null ? '—' : (v > 0 ? '+' : '') + (v * 100).toFixed(1).replace('.', ',') + ' pts';
const eur0 = (v: number) => new Intl.NumberFormat('de-DE', {style: 'currency', currency: 'EUR', maximumFractionDigits: 0}).format(v);
const day = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', {day: 'numeric', month: 'short'});
const toneLabel = (t: string) => t === 'du' ? 'Du' : 'Sie';
const mix = (o: Record<string, number>, label: (k: string) => string) => Object.entries(o).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${n} ${label(k)}`).join(' · ');
// The API takes dates and the channel as null when empty.
const body = (s: Spec) => ({...s, starts: s.starts || null, ends: s.ends || null, channel: s.channel || null});

function target(c: Spec) {
  const parts = [...c.value_tier, ...c.tenure, ...c.lines, ...(c.product ?? []), ...c.city];
  return parts.length ? parts.join(' · ') : 'All customers';
}

function LeftOut({a}: {a: Audience}) {
  if (!a.left_out.length) return null;
  return <details className="cp-leftout"><summary>{a.left_out.reduce((n, r) => n + r.customers, 0)} customers in the target group are left out</summary>
    <ul>{a.left_out.map(r => <li key={r.reason}><X size={13} aria-hidden="true" /><span>{r.label}</span><b>{r.customers}</b></li>)}</ul></details>;
}

function Numbers({a}: {a: Audience}) {
  return <dl className="cp-numbers">
    <div><dt>To contact</dt><dd>{a.contactable}<small>of {a.eligible} the offer fits</small></dd></div>
    <div><dt>Expected yes</dt><dd>{Math.round(a.expected_yes)}</dd></div>
    <div><dt>Expected customer value</dt><dd>{eur0(a.expected_gain_eur)}</dd></div>
    <div><dt>Control group</dt><dd>{a.control}<small>never contacted, to measure the effect</small></dd></div>
  </dl>;
}

// Step 2: the engine's segments; marketing switches them on or off, optionally after AI suggestions.
function SegmentList({a, chosen, setChosen, advice}: {a: Audience; chosen: string[]; setChosen: (k: string[]) => void; advice: Advice | null}) {
  const tip = (k: string) => advice?.segments.find(s => s.segment === k);
  return <ul className="cp-segments">{a.segments.map(s => {const on = chosen.includes(s.key), t = tip(s.key);
    return <li key={s.key} className={on ? 'on' : ''}>
      <label className="cp-seg-head"><input type="checkbox" checked={on} onChange={() => setChosen(on ? chosen.filter(k => k !== s.key) : [...chosen, s.key])} />
        <span><b>{s.need}</b><small>{s.channel_label}</small></span>
        {t && <em className={'cp-prio ' + t.priority}>{t.include ? (t.priority === 'high' ? 'Priority' : 'Include') : 'Skip'}</em>}
        {!s.recommended && <em className="cp-prio low">Not worth a contact</em>}
      </label>
      <dl className="cp-seg-facts">
        <div><dt>Customers</dt><dd>{s.customers}</dd></div>
        <div><dt>Expected yes</dt><dd>{s.expected_yes.toFixed(1).replace('.', ',')}</dd></div>
        <div><dt>Per contact</dt><dd>{eur(s.gain_per_contact_eur)}</dd></div>
        <div><dt>Usually online</dt><dd>{s.best_time}</dd></div>
      </dl>
      <p className="cp-seg-mix">{mix(s.tones, toneLabel)} · {mix(s.languages, l => l.toUpperCase())}</p>
      {t && <p className="cp-angle"><Sparkles size={13} aria-hidden="true" />{t.angle}</p>}
      <ul className="cp-examples">{s.examples.map(e => <li key={e.id}><b>{e.id}</b> {e.reason} <small>· {toneLabel(e.tone)} · {e.time.toLowerCase()}</small></li>)}</ul>
    </li>;})}</ul>;
}

function AdviceBox({advice}: {advice: Advice}) {
  return <section className="cp-advice" aria-label="Suggestions">
    <header><Sparkles size={15} aria-hidden="true" /><b>{advice.source === 'ai' ? 'AI suggestions' : 'Suggestions from the engine rules'}</b></header>
    <p>{advice.summary}</p>
    {!!advice.risks.length && <><h4>Risks</h4><ul>{advice.risks.map(r => <li key={r}>{r}</li>)}</ul></>}
    {!!advice.ideas.length && <><h4>Ideas</h4><ul>{advice.ideas.map(r => <li key={r}>{r}</li>)}</ul></>}
    {advice.note && <small>{advice.note}</small>}
  </section>;
}

export function NewCampaign({open, onClose, onCreated, prefill}: {open: boolean; onClose: () => void; onCreated: (c: Campaign) => void; prefill?: Partial<Spec>}) {
  const modal = useRef<HTMLDialogElement>(null);
  const {data: o} = useApi<Options>('/campaigns/options');
  const [step, setStep] = useState(0), [spec, setSpec] = useState<Spec>(EMPTY), [chosen, setChosen] = useState<string[]>([]);
  const [a, setA] = useState<Audience | null>(null), [advice, setAdvice] = useState<Advice | null>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  useEffect(() => {if (open) {if (prefill) setSpec(s => ({...s, ...prefill})); modal.current?.showModal();} else {modal.current?.close();setStep(0);setSpec(EMPTY);setChosen([]);setA(null);setAdvice(null);setBusy('');setError('')}}, [open]);
  useEffect(() => {if (o && !spec.offer) setSpec(s => ({...s, offer: o.offers[0].id}))}, [o, spec.offer]);
  // Recount totals when segments change, without losing the segment list the brief produced.
  useEffect(() => {
    if (step < 1 || !a) return;
    const ctl = new AbortController();
    request<Audience>('/campaigns/preview', 'POST', body({...spec, name: spec.name || 'Preview', segments: chosen}), ctl.signal).then(setA).catch(() => {});
    return () => ctl.abort();
  }, [chosen.join('|')]);

  const set = <K extends keyof Spec>(k: K, v: Spec[K]) => setSpec(s => ({...s, [k]: v}));
  const toggle = (f: Filter, v: string) => set(f, spec[f].includes(v) ? spec[f].filter(x => x !== v) : [...spec[f], v]);
  async function plan() {
    setBusy('plan');setError('');setAdvice(null);
    try {const r = await request<Audience>('/campaigns/preview', 'POST', body({...spec, segments: []}));setA(r);setChosen(r.segments.filter(s => s.included).map(s => s.key));setStep(1)}
    catch (e) {setError((e as Error).message)} finally {setBusy('')}
  }
  async function suggest() {
    setBusy('suggest');setError('');
    try {const r = await request<Advice>('/campaigns/suggest', 'POST', body(spec));setAdvice(r);setChosen(r.segments.filter(s => s.include).map(s => s.segment))}
    catch (e) {setError((e as Error).message)} finally {setBusy('')}
  }
  async function create() {
    setBusy('create');setError('');
    try {onCreated(await request<Campaign>('/campaigns', 'POST', body({...spec, segments: chosen})))}
    catch (e) {setError((e as Error).message);setBusy('')}
  }
  const offer = o?.offers.find(p => p.id === spec.offer), included = a?.segments.filter(s => chosen.includes(s.key)) || [];

  return <dialog ref={modal} className="developer-dialog campaign-dialog" aria-labelledby="campaign-title" onCancel={e => {e.preventDefault();if (!busy) onClose()}}>
    <div className="developer-dialog-header"><div><Megaphone size={21} /><div><h2 id="campaign-title">New personalised campaign</h2><p>You bring the offer and the goal. The engine plans every customer individually.</p></div></div><button className="button icon-button" aria-label="Close new campaign" disabled={!!busy} onClick={onClose}><X size={19} /></button></div>
    <ol className="cp-steps" aria-label="Steps">{STEPS.map((s, i) => <li key={s} className={i === step ? 'now' : i < step ? 'done' : ''} aria-current={i === step ? 'step' : undefined}><span>{i < step ? <Check size={12} /> : i + 1}</span>{s}</li>)}</ol>
    <div className="developer-dialog-content">{STATIC_MODE ? <div className="notice">This is a read-only demo. Start the full app to create campaigns.</div> : !o ? <Loading /> : <>
      {error && <div className="notice" role="alert">{error}</div>}

      {step === 0 && <div className="cp-form">
        <label className="cp-wide">Name<input value={spec.name} maxLength={80} placeholder="e.g. Autumn mobile for energy customers" onChange={e => set('name', e.target.value)} /></label>
        <label className="cp-wide">Goal<textarea rows={2} value={spec.goal} maxLength={500} placeholder="What should this campaign achieve, and for whom? e.g. Win energy customers for a mobile contract before the end of the year." onChange={e => set('goal', e.target.value)} /></label>
        <label className="cp-wide">Offer<select value={spec.offer} onChange={e => set('offer', e.target.value)}>{o.offers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>{offer?.description && <small>{offer.description}</small>}</label>
        <label className="cp-wide">Channel<select value={spec.channel} onChange={e => set('channel', e.target.value)}><option value="">Each customer's own best channel (recommended)</option>{o.channels.map(c => <option key={c.id} value={c.id}>Only {c.name}</option>)}</select></label>
        {FILTERS.map(([f, label]) => <fieldset key={f} className="cp-wide"><legend>{label} <small>(optional)</small></legend><div className="cp-chips">{o[f].map(v => <button key={v} type="button" aria-pressed={spec[f].includes(v)} className={spec[f].includes(v) ? 'on' : ''} onClick={() => toggle(f, v)}>{spec[f].includes(v) && <Check size={12} />}{v}</button>)}</div></fieldset>)}
        <label>City<select value={spec.city[0] || ''} onChange={e => set('city', e.target.value ? [e.target.value] : [])}><option value="">All cities</option>{o.city.map(c => <option key={c}>{c}</option>)}</select></label>
        <div className="cp-dates"><label>Starts<input type="date" value={spec.starts} onChange={e => set('starts', e.target.value)} /></label><label>Ends<input type="date" value={spec.ends} min={spec.starts || undefined} onChange={e => set('ends', e.target.value)} /></label></div>
      </div>}

      {step === 1 && a && <>
        <Numbers a={a} />
        <div className="cp-bar"><p>The engine grouped the customers this offer fits by their personal need and their best channel. Switch segments on or off.</p>
          <button className="button" disabled={!!busy || !a.segments.length} onClick={suggest}>{busy === 'suggest' ? <LoaderCircle className="loading-spin" size={15} /> : <Sparkles size={15} />}Suggest who and how</button></div>
        {advice && <AdviceBox advice={advice} />}
        {a.segments.length ? <SegmentList a={a} chosen={chosen} setChosen={setChosen} advice={advice} /> : <div className="notice">This offer fits no one in the target group who can be contacted. Widen the target group or choose another offer.</div>}
        <LeftOut a={a} />
      </>}

      {step === 2 && a && <div className="cp-messages">
        <p className="cp-lead">Every customer gets the approved text for this offer in their own language and Du or Sie, on their own channel, at the time they are usually online. The personal reason decides who gets it and guides the call team.</p>
        {included.map(s => {const t = advice?.segments.find(x => x.segment === s.key);
          return <section key={s.key}><h4>{s.need} <small>· {s.channel_label} · {s.customers} customers · usually online: {s.best_time.toLowerCase()}</small></h4>
            {t && <p className="cp-angle"><Sparkles size={13} aria-hidden="true" />{t.angle}</p>}
            <div className="cp-variants">{Object.entries(s.messages).map(([k, m]) => <article key={k}><span>{k.split('-')[0].toUpperCase()} · {toneLabel(k.split('-')[1])}</span><b>{m.subject}</b><p>{m.body}</p></article>)}</div>
            <p className="cp-why">Personal reasons, e.g. {s.examples.map(e => <span key={e.id}><b>{e.id}</b>: {e.reason}</span>)}</p>
          </section>;})}
      </div>}

      {step === 3 && a && <div className="cp-review">
        <dl>
          <div><dt>Campaign</dt><dd>{spec.name}</dd></div>
          {spec.goal && <div><dt>Goal</dt><dd>{spec.goal}</dd></div>}
          <div><dt>Offer</dt><dd>{offer?.name}</dd></div>
          <div><dt>Target group</dt><dd>{target(spec)}</dd></div>
          <div><dt>Channel</dt><dd>{spec.channel ? 'Only ' + o.channels.find(c => c.id === spec.channel)?.name : 'Each customer’s own best channel'}</dd></div>
          <div><dt>Segments</dt><dd>{included.map(s => s.key).join('; ') || '—'}</dd></div>
          {spec.starts && <div><dt>Runs</dt><dd>{day(spec.starts)}{spec.ends ? ' – ' + day(spec.ends) : ''}</dd></div>}
        </dl>
        <Numbers a={a} />
      </div>}

      <div className="developer-key-actions cp-nav">
        {step > 0 && <button className="button" disabled={!!busy} onClick={() => setStep(step - 1)}><ArrowLeft size={15} />Back</button>}
        {step === 0 && <button className="button primary" disabled={!!busy || !spec.name.trim() || !spec.offer} onClick={plan}>{busy === 'plan' ? <LoaderCircle className="loading-spin" size={15} /> : <ArrowRight size={15} />}Plan the audience</button>}
        {(step === 1 || step === 2) && <button className="button primary" disabled={!!busy || !chosen.length} onClick={() => setStep(step + 1)}><ArrowRight size={15} />{step === 1 ? 'See the messages' : 'Review'}</button>}
        {step === 3 && <button className="button primary" disabled={!!busy || !a?.contactable} onClick={create}>{busy === 'create' ? <LoaderCircle className="loading-spin" size={15} /> : <Plus size={15} />}Create campaign</button>}
        <button className="button" disabled={!!busy} onClick={onClose}>Cancel</button>
      </div>
      <p className="developer-key-note">Saved as a draft. Nothing is sent: launching records the approval and starts simulated tracking. The 10 % control group is never contacted.</p>
    </>}</div>
  </dialog>;
}

// Cumulative "said yes" per day against the forecast, with a day-by-day hover readout.
function Timeline({t}: {t: Tracking}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 560, H = 180, L = 36, R = 64, T = 12, B = 26;
  const pts = t.timeline, max = Math.max(1, ...pts.map(p => Math.max(p.yes, p.expected_yes)));
  const x = (i: number) => L + (pts.length > 1 ? i / (pts.length - 1) : 0) * (W - L - R), y = (v: number) => T + (1 - v / max) * (H - T - B);
  const line = (f: (p: typeof pts[0]) => number) => pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(f(p)).toFixed(1)}`).join('');
  const ticks = [0, Math.round(max / 2), Math.round(max)].filter((v, i, all) => all.indexOf(v) === i);
  const h = hover == null ? null : pts[hover], last = pts[pts.length - 1];
  return <figure className="cp-chart">
    <figcaption><b>Said yes over time</b><span className="cp-legend"><i className="actual" />Said yes<i className="forecast" />Forecast</span></figcaption>
    <div className="cp-chart-box">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Said yes after ${last.day} days: ${last.yes}, forecast ${last.expected_yes.toFixed(1)}`}
        onMouseMove={e => {const r = e.currentTarget.getBoundingClientRect();const px = (e.clientX - r.left) / r.width * W;setHover(Math.max(0, Math.min(pts.length - 1, Math.round((px - L) / (W - L - R) * (pts.length - 1)))))}} onMouseLeave={() => setHover(null)}>
        {ticks.map(v => <g key={v}><line className="grid" x1={L} x2={W - R} y1={y(v)} y2={y(v)} /><text className="axis" x={L - 6} y={y(v) + 4} textAnchor="end">{v}</text></g>)}
        <text className="axis" x={L} y={H - 6}>Day 1</text><text className="axis" x={W - R} y={H - 6} textAnchor="end">Day {last.day}</text>
        <path className="forecast" d={line(p => p.expected_yes)} />
        <path className="actual" d={line(p => p.yes)} />
        <text className="end" x={W - R + 6} y={y(last.yes) + 4}>{last.yes} yes</text>
        <text className="end muted" x={W - R + 6} y={y(last.expected_yes) + (Math.abs(y(last.yes) - y(last.expected_yes)) < 14 ? 16 : 4)}>{last.expected_yes.toFixed(0)} forecast</text>
        {h && hover != null && <><line className="cross" x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} /><circle className="actual" cx={x(hover)} cy={y(h.yes)} r={4} /></>}
      </svg>
      {h && hover != null && <div className="cp-tip" style={{left: `${x(hover) / W * 100}%`}}><b>Day {h.day}</b><span>{h.sent} sent</span><span>{h.yes} said yes</span><span>{h.expected_yes.toFixed(1).replace('.', ',')} forecast</span></div>}
    </div>
  </figure>;
}

function Breakdowns({title, column, rows}: {title: string; column: string; rows: Breakdown[]}) {
  return <div className="table-wrap"><table className="cp-table"><caption>{title}</caption><thead><tr><th>{column}</th><th className="right">Sent</th><th className="right">Said yes</th><th className="right">vs. control</th><th className="right">Value won</th></tr></thead>
    <tbody>{rows.map(r => <tr key={r.key}><td>{r.label}</td><td className="right">{r.sent}</td><td className="right">{r.yes} <small>{pct(r.yes_rate)}</small></td><td className={'right ' + (r.uplift != null && r.uplift > 0 ? 'good' : r.uplift != null && r.uplift <= 0 && r.sent >= 8 ? 'bad' : '')}>{r.sent < 8 ? <small>too few</small> : pts(r.uplift)}</td><td className="right">{eur0(r.value_won_eur)}</td></tr>)}</tbody></table></div>;
}

const ICON = {good: ThumbsUp, warn: TriangleAlert, idea: Lightbulb};

function Monitor({c, busy, onFollowUp}: {c: Campaign; busy: boolean; onFollowUp: () => void}) {
  const t = c.tracking!;
  return <>
    <dl className="cp-kpis">
      <div><dt>Sent</dt><dd>{t.sent}<small>{t.seen} saw it</small></dd></div>
      <div><dt>Said yes</dt><dd>{t.yes}<small>{pct(t.yes_rate)}</small></dd></div>
      <div><dt>Control group</dt><dd>{pct(t.control_rate)}<small>{t.control_yes} of {t.control} without contact</small></dd></div>
      <div><dt>Uplift</dt><dd className={t.uplift != null && t.uplift > 0 ? 'good' : ''}>{pts(t.uplift)}</dd></div>
      <div><dt>Value won</dt><dd>{eur0(t.value_won_eur)}<small>forecast {eur0(t.expected_gain_eur)}</small></dd></div>
    </dl>
    <Timeline t={t} />
    <div className="cp-tables"><Breakdowns title="By segment" column="Segment" rows={t.segments} /><Breakdowns title="By channel" column="Channel" rows={t.channels} /></div>
    {!!c.insights.length && <section className="cp-insights" aria-label="Insights and improvements"><h4>Insights and improvements</h4>
      <ul>{c.insights.map(i => {const Icon = ICON[i.kind];return <li key={i.title} className={i.kind}><Icon size={16} aria-hidden="true" /><div><b>{i.title}</b><p>{i.text}</p></div></li>;})}</ul>
      <button className="button primary" disabled={busy} onClick={onFollowUp}><Repeat2 size={15} />Create improved follow-up</button>
    </section>}
    <p className="cp-sim">Simulated results: nothing is sent in this demo, so reactions are drawn from each customer's chance of yes. Uplift compares with the campaign's control group.</p>
  </>;
}

export function CampaignsTab({revision, names, onNew, onChanged, notify}: {revision: number; names: Record<string, string>; onNew: () => void; onChanged: () => void; notify: (s: string) => void}) {
  const {data, error} = useApi<{items: Campaign[]}>('/campaigns', revision);
  const [busy, setBusy] = useState(0);
  async function act(c: Campaign, how: 'launch' | 'delete' | 'follow-up') {
    setBusy(c.id);
    try {
      if (how === 'launch') await request('/campaigns/' + c.id + '/launch', 'POST');
      else if (how === 'follow-up') await request('/campaigns/' + c.id + '/follow-up', 'POST');
      else await request('/campaigns/' + c.id, 'DELETE');
      onChanged();
      notify(how === 'launch' ? `“${c.name}” is running. Nothing was sent; tracking results are simulated.` : how === 'follow-up' ? `Improved follow-up of “${c.name}” saved as a draft, without the segments the results say to drop.` : `Draft “${c.name}” deleted.`);
    } catch (e) {notify((e as Error).message)} finally {setBusy(0)}
  }
  if (error) return <Loading error={error} />;
  if (!data) return <Loading />;
  if (!data.items.length) return <div className="cp-empty"><Megaphone size={26} /><h3>No campaigns yet</h3><p>Bring an offer and a goal. The engine plans every customer individually: their own channel, tone, timing and reason.</p><button className="button primary" onClick={onNew}><Plus size={15} />New campaign</button></div>;
  return <div className="cp-list">{data.items.map(c => {const a = c.audience, on = a.segments.filter(s => s.included);
    return <Panel key={c.id} title={c.name} subtitle={`${names[c.offer] || c.offer} · ${c.channel ? 'one channel' : 'personal channels'} · ${target(c)}${c.starts ? ' · ' + day(c.starts) + (c.ends ? ' – ' + day(c.ends) : '') : ''}`}
      action={<span className={'cp-status ' + c.status}>{c.status === 'running' ? 'Running' : 'Draft'}</span>}>
      <div className="cp-body">
        {c.goal && <p className="cp-goal"><b>Goal:</b> {c.goal}</p>}
        {c.follows && <p className="cp-goal"><Repeat2 size={13} aria-hidden="true" /> Follow-up of campaign #{c.follows}, improved from its results.</p>}
        {c.tracking ? <Monitor c={c} busy={!!busy} onFollowUp={() => act(c, 'follow-up')} /> : <>
          <Numbers a={a} />
          <ul className="cp-chosen">{on.map(s => <li key={s.key}><b>{s.need}</b> · {s.channel_label} · {s.customers} customers · <Clock3 size={12} aria-hidden="true" /> {s.best_time.toLowerCase()}</li>)}</ul>
          <div className="cp-actions"><button className="button primary" disabled={!!busy || !a.contactable} onClick={() => act(c, 'launch')}><Rocket size={14} />Approve & launch</button><button className="button" disabled={!!busy} onClick={() => act(c, 'delete')}><Trash2 size={14} />Delete</button></div>
        </>}
      </div>
    </Panel>;
  })}</div>;
}
