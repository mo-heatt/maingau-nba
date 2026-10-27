import {useState} from 'react';
import {Radar, ArrowRight, Check, Undo2} from 'lucide-react';
import {useApi} from '../api';
import {Loading, Metric, PageTitle, Panel} from '../components/ui';

export type RadarCard = {
  customer_id: string; city: string; waiting_since: string; days_waiting: number; contacts: number;
  dunning_level: number; sales_while_waiting: number; why: string[]; quote: string;
  timeline: {at: string; kind: 'contact' | 'sale' | 'billing'; label: string; text: string; solved: boolean; status: string}[];
  actions: {id: string; label: string; done: string}[];
};
export type RadarData = {as_of: string; open_complaints: number; rules: string[]; cards: RadarCard[]};

// Clicks stay in this browser only: nothing reaches a real system.
const STORE = 'case-radar-actions';
function loadDone(): Record<string, boolean> { try { return JSON.parse(localStorage.getItem(STORE) || '{}'); } catch { return {}; } }
export function useRadarActions() {
  const [done, setDone] = useState<Record<string, boolean>>(loadDone);
  const toggle = (key: string) => setDone(d => { const n = {...d, [key]: !d[key]}; try { localStorage.setItem(STORE, JSON.stringify(n)); } catch { /* session only */ } return n; });
  return {done, toggle};
}

const d = (iso: string) => new Date(iso.replace(' ', 'T')).toLocaleDateString('en-GB', {day: 'numeric', month: 'short'});

// Every contact, sales message and billing step on one line, so the loop is visible at a glance.
function Track({c}: {c: RadarCard}) {
  return <ol className="radar-track">{c.timeline.map((t, i) =>
    <li key={i} className={'rt-' + t.kind + (t.solved ? ' solved' : '')}>
      <span className="rt-date">{d(t.at)}</span><i aria-hidden="true" />
      <span className="rt-text"><b>{t.label}</b> · {t.status}{t.text && t.kind === 'contact' ? <small>„{t.text.slice(0, 110)}{t.text.length > 110 ? '…' : ''}“</small> : null}</span>
    </li>)}</ol>;
}

export function RadarBox({c, onOpen, compact}: {c: RadarCard; onOpen?: () => void; compact?: boolean}) {
  const {done, toggle} = useRadarActions();
  return <section className={'radar-box' + (compact ? ' compact' : '')}>
    <header>
      <div><div className="eyebrow"><Radar size={12} /> Case Radar · stuck for {c.days_waiting} days</div>
        <h3>{onOpen ? <button className="link big" onClick={onOpen}>{c.customer_id} <ArrowRight size={14} /></button> : 'This customer is stuck in service'}<span className="muted"> {c.city}</span></h3></div>
      <div className="radar-actions">{c.actions.map(a => {const k = c.customer_id + ':' + a.id, on = !!done[k];
        return <button key={a.id} className={'button' + (on ? ' radar-done' : ' primary')} onClick={() => toggle(k)}>{on ? <><Check size={14} />{a.done}<Undo2 size={12} /></> : a.label}</button>;})}</div>
    </header>
    <ul className="radar-why">{c.why.map(w => <li key={w}>{w}</li>)}
      {c.sales_while_waiting > 0 && <li>Today's engine sent {c.sales_while_waiting} sales message{c.sales_while_waiting > 1 ? 's' : ''} while the customer was waiting. Ours blocks sales until this is solved.</li>}</ul>
    {c.quote && <blockquote>„{c.quote}“</blockquote>}
    {!compact && <Track c={c} />}
  </section>;
}

export default function ServiceFirst({revision, onSelect}: {revision: number; onSelect: (id: string) => void}) {
  const {data: r, error} = useApi<RadarData>('/radar', revision);
  if (error) return <Loading error={error} />;
  if (!r) return <Loading />;
  const reminders = r.cards.filter(c => c.dunning_level > 0).length, sales = r.cards.reduce((n, c) => n + c.sales_while_waiting, 0);
  return <>
    <PageTitle eyebrow="Case Radar" title="Service first" />
    <p className="page-intro">Customers stuck with an open complaint, and one click to stop the harm.</p>
    <div className="metrics"><Metric label="Stuck customers" value={r.cards.length} hint={'of ' + r.open_complaints + ' customers with an open complaint'} /><Metric label="Reminders during a complaint" value={reminders} /><Metric label="Sales messages while waiting" value={sales} /><Metric label="Longest wait" value={Math.max(...r.cards.map(c => c.days_waiting)) + ' days'} hint={'as of ' + d(r.as_of)} /></div>
    <Panel title="Stuck cases, most urgent first" subtitle={'Flagged when a complaint is open and: ' + r.rules.join('; or ')}>
      <div className="radar-list">{r.cards.map(c => <RadarBox key={c.customer_id} c={c} onOpen={() => onSelect(c.customer_id)} />)}</div>
    </Panel>
    <p className="small-text muted">Demo: clicks stay in this browser and reach no real system.</p>
  </>;
}
