import {ArrowRight, Check, X, Mail, MessageSquareText, AlertTriangle, ShieldAlert, BellOff, EyeOff, Scale, HeartCrack, CircleCheck} from 'lucide-react';
import type {LucideIcon} from 'lucide-react';
import type {ReactNode} from 'react';
import {useApi, eur, channel} from '../api';
import type {Customer, Catalog, Replay} from '../types';
import {Metric, Panel, Loading} from '../components/ui';

type Legacy = {actions: number; delivered: number; rules: number; consent_not_checked: number; unchecked_and_no_consent: number; sales_during_open_complaint: number; app_push: number; app_push_without_app: number; responses: Record<string, number>; agent_dismissed: number; agent_dismissed_upset: number; agent_suggestions: number};
type OverviewData = {summary: {customers: number; expected_gain_eur: number; offers: number; service_fixes: number; held_out: number; approved: number; no_contact: number}; actions: Record<string, number>; violations: number; legacy: Legacy; acceptance: {treated?: number; control?: number}; cases: {service: string; sale: string}};
type View = 'overview' | 'recommendations' | 'service' | 'marketing' | 'customers' | 'method';

const pct = (v = 0, d = 0) => (v * 100).toFixed(d).replace('.', ',') + ' %';
const signed = (v: number) => (v > 0 ? '+' : '') + eur(v);
const day = (iso: string) => new Date(iso.slice(0, 10) + 'T12:00:00').toLocaleDateString('en-GB', {day: 'numeric', month: 'short'});

const STEPS: [string, string][] = [
  ['Profile', 'Everything about one customer in one row'],
  ['When', 'Every night, and right away when something happens'],
  ['Rules', 'Angry or unpaid bill? Fix, don’t sell. No consent? Don’t use the channel'],
  ['Best offer', 'Chance of yes × what Maingau earns − cost. Biggest wins, or nothing'],
  ['Channel & tone', 'Where they said yes and will see it soon; Du or Sie as they write'],
  ['Message', 'Approved German text; AI only writes inside it'],
  ['Approve & send', 'Marketing says yes; 1 in 10 is held back to measure'],
];

const RULES = ['Consent is binding, per channel', 'Exclusions beat offers: complaint, dunning, cancellation', 'Human in the loop: nothing is sent without approval', 'Profiling only with consent, AI text too', 'No manipulation: approved texts, no personal prices or fake urgency', 'Payment data only as an exclusion', 'Every decision logged with inputs, rules, scores', 'Mock data only', 'Customer texts in German, Du or Sie'];

type Line = {date: string; kind: 'offer' | 'customer' | 'event'; text: string; bad?: boolean};

function oldTimeline(c: Customer, names: Record<string, string>, events: Replay['changes']): Line[] {
  const lines: Line[] = [];
  for (const h of c.history) {
    const noApp = h.channel === 'app_push' && !c.app_installed;
    const reaction = h.response === 'held_out' ? 'held back (control group)' : h.response === 'ignored' ? 'no reaction' : h.response;
    lines.push({date: h.date, kind: 'offer', bad: h.response !== 'held_out', text: `${names[h.offer] || h.offer} by ${channel(h.channel).toLowerCase()}${noApp ? ', but the customer has no app' : ''}: ${reaction}.`});
  }
  for (const t of c.tickets) lines.push({date: t.created_at, kind: 'customer', text: t.text ? `“${t.text.length > 110 ? t.text.slice(0, 107) + '…' : t.text}”` : `Customer contacts service about ${t.category}.`});
  for (const e of events) lines.push({date: e.occurred_at, kind: 'event', bad: true, text: e.note + '.'});
  return lines.sort((a, b) => a.date.localeCompare(b.date));
}

export default function Overview({revision, onGo, onSelect}: {revision: number; onGo: (v: View) => void; onSelect: (id: string) => void}) {
  const {data: o, error} = useApi<OverviewData>('/overview', revision);
  const {data: cat} = useApi<Catalog>('/catalog');
  const {data: replay} = useApi<Replay>('/replay', revision);
  const {data: svc} = useApi<Customer>('/customers/' + (o?.cases.service || 'MG-100004'), revision);
  const {data: sale} = useApi<Customer>('/customers/' + (o?.cases.sale || 'MG-100068'), revision);
  if (error) return <Loading error={error} />;
  if (!o) return <Loading />;
  const L = o.legacy, resp = L.responses, total = Object.values(resp).reduce((a, b) => a + b, 0);
  const names: Record<string, string> = Object.fromEntries((cat?.products || []).map(p => [p.product_id, p.product_name]));
  const left = (o.actions.none || 0) + (o.actions.wait || 0) + (o.actions.human_review || 0);
  const evFor = (id?: string) => (replay?.changes || []).filter(e => e.customer_id === id);
  const bestSale = svc ? svc.candidates.filter(k => k.offer !== 'P-SV-01').sort((a, b) => b.dclv - a.dclv)[0] : undefined;
  const sentSvc = svc ? svc.history.filter(h => h.response !== 'held_out').length : 0;
  return <div className="overview">
    <section className="ov-hero">
      <div className="eyebrow">MAINGAU challenge · One customer, every channel</div>
      <h1>For every customer, the one step worth the most: sell, fix, or wait.</h1>
      <p>Maingau already has every source under one customer_id. What was missing is the decision on top. Our engine checks the rules, scores every possible action by the expected gain in customer lifetime value, and proposes the best one with the right channel and tone. Marketing approves; every decision is explained and logged.</p>
    </section>

    <div className="metrics">
      <Metric label="Expected gain in customer value" value={eur(o.summary.expected_gain_eur)} hint={`across ${o.summary.customers} customers, this run`} />
      <Metric label="Consent or exclusion violations" value={o.violations} hint={`today’s engine: ${L.unchecked_and_no_consent} contacts without consent`} />
      <Metric label="Problems fixed before selling" value={o.summary.service_fixes} hint="complaint or unpaid bill: service first" />
      <Metric label="Left alone on purpose" value={left} hint="nothing worth a contact, limit reached, or a person decides" />
    </div>

    <Panel title="What Maingau asked for" subtitle="The three questions and hard rules from the brief, and where each is built">
      <div className="ov-ask">
        <div><span className="ov-tag">Built</span><h3>Decide</h3><p className="muted">Which offer, channel and tone per customer, ranked by expected CLV gain?</p><p>One action per customer with channel, Du/Sie and expected gain.</p><button className="button small" onClick={() => onGo('recommendations')}>Recommendations <ArrowRight size={12} /></button></div>
        <div><span className="ov-tag">Built</span><h3>Explain</h3><p className="muted">Can a marketer see in one line why, and change it?</p><p>A one-line reason, every option scored, rules to steer, and overrides with a note.</p><button className="button small" onClick={() => onGo('marketing')}>Marketing <ArrowRight size={12} /></button></div>
        <div><span className="ov-tag">Concept + demo</span><h3>Learn</h3><p className="muted">How do reactions improve it, and how do you prove cause?</p><p>A stable 10% control group; uplift feeds back into the chance of yes.</p><button className="button small" onClick={() => onGo('method')}>How it works <ArrowRight size={12} /></button></div>
      </div>
      <ul className="ov-rules">{RULES.map(r => <li key={r}><Check size={14} />{r}</li>)}</ul>
    </Panel>

    <Panel title="5 problems in today’s rule engine" subtitle={`Found in Maingau’s own data: ${L.actions.toLocaleString('en-GB')} decisions from June to September, made by ${L.rules} broad rules that look at segments, not at the person. Each card shows the problem, why it matters and how our engine fixes it.`}>
      <div className="ov-problems">
        <Problem tone="critical" Icon={ShieldAlert} tag="Legal risk" figure={String(L.consent_not_checked)}
          text={<>actions skipped the consent check; <b>{L.unchecked_and_no_consent}</b> reached a channel without consent.</>}
          why="Contacting without consent breaks GDPR and UWG rules."
          fix={`Consent is checked for every channel, every time. Violations in our run: ${o.violations}.`} />
        <Problem tone="warning" Icon={BellOff} tag="Wasted contact" figure={`${L.app_push_without_app}/${L.app_push}`}
          text="app pushes went to customers who don’t have the app."
          why="These messages could never arrive."
          fix="A channel is only used where the customer can see it: app installed, regular portal logins." />
        <Problem tone="warning" Icon={EyeOff} tag="Ignored" figure={pct(((resp.ignored || 0) + (resp.dismissed || 0)) / (total || 1))}
          text="of contacts were ignored or dismissed."
          why="The same message to a whole segment teaches customers to ignore Maingau."
          fix={`One offer per person, ranked by expected gain. If nothing is worth it, no contact (${o.summary.no_contact} customers left alone).`} />
        <Problem tone="warning" Icon={Scale} tag="No proof of effect" figure={`${pct(o.acceptance.treated, 1)} vs ${pct(o.acceptance.control, 1)}`}
          text="bought after a contact vs. without one."
          why="Contacts get credit for purchases that would have happened anyway. The control group is small, so treat the gap with care."
          fix="A stable 10% control group measures what each contact really adds." />
        <Problem tone="warning" Icon={HeartCrack} tag="Hurts service" figure={`${L.agent_dismissed_upset}/${L.agent_dismissed}`}
          text="sales tips dismissed by service agents because the customer was upset."
          why="Selling to an upset customer makes the problem worse."
          fix="Service first: complaints and unpaid bills get a fix, not an offer. Stuck cases go on the Case Radar." />
      </div>
    </Panel>

    <Panel title="Our engine in seven steps" subtitle="Step 8, learn: after two weeks we compare contacted customers with the 1 in 10 held back. What really works is offered more often.">
      <div className="ov-steps">{STEPS.map(([t, x], i) => <div key={t}><span>{i + 1}</span><h3>{t}</h3><p>{x}</p></div>)}</div>
    </Panel>

    <Panel title="One real customer: their engine vs. ours" subtitle="Every line is taken from Maingau’s mock data and today’s event stream.">
      {!svc ? <Loading /> : <>
        <p className="ov-who">Customer <button className="link" onClick={() => onSelect(svc.id)}>{svc.id}</button>, {svc.city}, customer since {svc.since.slice(0, 4)}.</p>
        <div className="ov-vs">
          <div className="ov-side old">
            <header><div className="eyebrow">Today’s rule engine</div><h3>{sentSvc} offers, no help</h3></header>
            <ul className="ov-tl">{oldTimeline(svc, names, evFor(svc.id)).map((l, i) => <li key={i} className={l.kind}><span className="d">{day(l.date)}</span><span className="i">{l.kind === 'customer' ? <MessageSquareText size={14} /> : l.kind === 'event' ? <AlertTriangle size={14} /> : l.bad ? <X size={14} /> : <Mail size={14} />}</span><span>{l.text}</span></li>)}</ul>
            <div className="ov-out">Result: no sale, an unhappy customer with a <b>{pct(svc.value.churn)}</b> chance of leaving. Service problems have cut their value by <b>{eur(-svc.value.clv_service_impact)}</b>.</div>
          </div>
          <div className="ov-side new">
            <header><div className="eyebrow">Our engine, 1 October</div><h3>{svc.decision.action === 'service' ? 'Stop selling, fix the problem' : svc.decision.name}</h3></header>
            <ul className="ov-tl">
              <li><span className="d">Profile</span><span className="i">1</span><span>{svc.open_tickets.length} open case{svc.open_tickets.length === 1 ? '' : 's'}{svc.open_tickets[0] ? ` (${svc.open_tickets[0].category})` : ''}, CLV {eur(svc.value.clv)}, writes {svc.tone === 'du' ? 'informally' : 'formally'}.</span></li>
              <li><span className="d">Rules</span><span className="i bad"><X size={14} /></span><span>{svc.decision.log.find(x => x.toLowerCase().includes('block') || x.toLowerCase().includes('exclusion')) || svc.decision.log[0] || 'Sales content blocked.'}</span></li>
              <li><span className="d">Best</span><span className="i good"><Check size={14} /></span><span>{svc.decision.name} worth <b>{signed(svc.decision.expected_gain_eur)}</b>{bestSale ? <>; the best sales offer would be worth {signed(bestSale.dclv)}</> : null}.</span></li>
              <li><span className="d">Channel</span><span className="i good"><Check size={14} /></span><span>{channel(svc.decision.channel)}, addressed with “{svc.decision.tone === 'du' ? 'Du' : 'Sie'}”, no offer.</span></li>
              {evFor(svc.id).length > 0 && <li><span className="d">Events</span><span className="i good"><Check size={14} /></span><span>{evFor(svc.id).length} new event{evFor(svc.id).length === 1 ? '' : 's'} today re-checked the decision: {svc.decision.name.toLowerCase()} stays the plan.</span></li>}
              <li><span className="d">Radar</span><span className="i good"><Check size={14} /></span><span>Flagged as stuck: came back unsolved, and reminders are running during the complaint. One click pauses the reminders. <button className="link" onClick={() => onGo('service')}>Service first</button></span></li>
              <li><span className="d">Approve</span><span className="i good"><Check size={14} /></span><span>Marketing creates the service task; the decision is logged with its reason.</span></li>
            </ul>
            <div className="ov-out">Result: no more sales pressure, a person solves the problem, expected <b>{signed(svc.decision.expected_gain_eur)}</b> in customer value.</div>
          </div>
        </div>
      </>}
      {sale && <div className="ov-sale"><div className="eyebrow">And a sale done right</div>
        <p><button className="link" onClick={() => onSelect(sale.id)}>{sale.id}</button> · today: {sale.history.length ? sale.history.map(h => `${names[h.offer] || h.offer} by ${channel(h.channel).toLowerCase()}${h.channel === 'app_push' && !sale.app_installed ? ' (no app installed)' : ''}, ${h.response === 'ignored' ? 'no reaction' : h.response}`).join('; ') : 'no earlier contact'}.</p>
        <p>Ours: <b>{sale.decision.name}</b> by {channel(sale.decision.channel).toLowerCase()}, “{sale.decision.tone === 'du' ? 'Du' : 'Sie'}”, expected <b>{signed(sale.decision.expected_gain_eur)}</b>. Why: {sale.decision.reason.split('. Via ')[0]}.</p></div>}
    </Panel>

    <div className="ov-go">
      {([['recommendations', 'Recommendations', 'Every customer: offer, channel, tone, expected gain and reason.'], ['customers', 'Customer 360°', 'For service agents: status, value, the best action and why.'], ['service', 'Service first', 'Case Radar: stuck customers, why, and one click to stop the harm.'], ['marketing', 'Marketing dashboard', 'Set limits, priorities and channels; approve texts and actions.'], ['method', 'How it works', 'The pipeline, event replay, learning loop and target architecture.']] as [View, string, string][]).map(([v, t, x]) => <button key={v} onClick={() => onGo(v)}><h3>{t} <ArrowRight size={14} /></h3><p>{x}</p></button>)}
    </div>
  </div>;
}

// One problem found in the current engine: what, why it matters, and how our engine fixes it.
function Problem({tone, Icon, tag, figure, text, why, fix}: {tone: 'critical' | 'warning'; Icon: LucideIcon; tag: string; figure: string; text: ReactNode; why: string; fix: string}) {
  return <article className={'ov-problem ' + tone}>
    <header><span className="ov-problem-icon" aria-hidden="true"><Icon size={18} /></span><span className="ov-problem-tag">{tag}</span></header>
    <strong>{figure}</strong>
    <p className="ov-problem-what">{text}</p>
    <p className="ov-problem-why">{why}</p>
    <p className="ov-problem-fix"><CircleCheck size={15} aria-hidden="true" /><span><b>Our fix:</b> {fix}</span></p>
  </article>;
}
