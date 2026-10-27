import {useApi} from '../api';
import type {Replay} from '../types';
import {Metric, PageTitle, Panel, Loading} from '../components/ui';

// The team's seven steps, in the words we use in the pitch.
const steps: [string, string, string][] = [
  ['1', 'Profile', 'Everything about one customer in one row: products, value, problems, consent, behaviour, how they write. Late records are filtered at the snapshot.'],
  ['2', 'Snapshot', 'The workbook is imported into SQLite once. Customer profiles are built at startup; event replay is a dry run and does not overwrite them.'],
  ['3', 'Rules', 'Complaint or unpaid bill: fix, don’t sell. Cancellation: a person decides. No consent: channel removed. Already owned or contacted too often: skip. Stuck service cases go on the Case Radar.'],
  ['4', 'Best offer', 'Every allowed offer gets a value: chance of yes × what Maingau earns − cost. The highest wins; if nothing is worth a contact, do nothing.'],
  ['5', 'Channel & tone', 'Only channels with consent, where the customer will see it soon (3+ portal logins in 90 days for a pop-up). Du or Sie from their own words.'],
  ['6', 'Message', 'AI writes channel-specific German copy for the validated proposal and server quote. Source, number and tone checks allow at most two automatic copy repairs.'],
  ['7', 'Preview & review', 'Decisions and materials are saved in SQLite. A stable 10% control group is held back. All output is preview-only: no external sending.'],
];

// Why each remaining event type is logged but does not change a decision.
const IGNORED: Record<string, string> = {
  page_viewed: 'Not used yet. A visit to the offers or tariff page could become an interest signal later.',
  newsletter_opened: 'Opens are unreliable (Apple Mail opens automatically); clicks are used instead.',
  charge_session_started: 'Only failed charging sessions change a decision.',
  charge_session_completed: 'Only failed charging sessions change a decision.',
  meter_reading_submitted: 'Routine meter reading; no decision depends on it.',
  hems_daily_summary: 'One day of solar data; the engine uses the longer usage profile.',
};

export default function Method({revision}: {revision: number}) {
  const {data: r, error} = useApi<Replay>('/replay', revision);
  return <>
    <PageTitle eyebrow="How it works" title="Sell when it helps, fix when it hurts." />
    <p className="page-intro">Shared source data and policy on the server. The engine baseline and AI selection are labelled separately; neither can rewrite recorded consent.</p>
    <div className="ov-steps method-steps">{steps.map(([n, title, text]) => <div key={n}><span>{n}</span><h3>{title}</h3><p>{text}</p></div>)}</div>
    <div className="notice learn-note"><b>8 · Learn.</b> Future learning: compare delivered campaigns against the control group once outcomes mature. Today responses are recorded for demonstration; online retraining and causal uplift learning are not implemented.</div>

    <Panel title="Current MVP: from source to offer" subtitle="React → FastAPI → SQLite snapshot → policy and AI → saved preview"><div className="method-runtime-flow">{[['Source snapshot','SQLite source records; original consent stays read only.'],['Customer 360','Products, signals, service, estimated value and recorded permissions.'],['Decision','Engine comparison or AI catalogue analysis with source citations.'],['Channel checks','Consent, double opt-in, contact limits, service rules and holdout.'],['Material','Concrete quote and bounded AI copy repair, then saved preview.']].map(([title,description])=><div key={title}><b>{title}</b><p>{description}</p></div>)}</div><p className="method-text">Recorded consent and action availability are different: a control-group customer may have Newsletter consent while campaign generation is held back. Browser reads are reused for 30 seconds; saved decisions and materials persist in SQLite.</p><a className="button" href="https://github.com/mo-heatt/maingau-nba/blob/integration/test-main-ai/docs/architecture.md" target="_blank" rel="noreferrer">Architecture & flow diagrams ↗</a></Panel>
    <Panel title="How value is estimated" subtitle="Explicit assumptions, not guaranteed revenue">
      <div className="formula">p × (CLV accepted − CLV now) + (1 − p) × (CLV rejected − CLV now) − contact cost</div>
      <p className="method-text">p comes from Maingau’s action history, smoothed so small groups don’t mislead, and only uses offers whose 14-day result is already known. Strong and medium signals and portal reach use configurable assumptions to confirm with Maingau. This is not yet a causal uplift model; the control group is how we get there.</p>
    </Panel>

    <Panel title="Target architecture: Databricks with MCP" subtitle="How this prototype would run at Maingau">
      <div className="arch-grid">
        <div><div className="eyebrow">Sources, one customer_id</div><ul><li><b>CRM, billing, telco</b> CDC and nightly files</li><li><b>Shop, HEMS, Autostrom</b> webhooks and APIs</li><li><b>Consent platform</b> events, binding within a minute</li><li><b>Newsletter, portal</b> hourly and streaming</li></ul></div>
        <div className="arch-core"><div className="eyebrow">Databricks</div>
          <div className="arch-row"><div><b>Bronze</b> raw events and files with arrival time</div><div><b>Silver</b> customer_state, one row per customer</div><div><b>Gold</b> scored options and the decision log</div></div>
          <div className="arch-row"><div><b>Scoring job</b> nightly, plus per event</div><div><b>MLflow</b> acceptance rates and uplift</div><div><b>Model Serving</b> LLM inside approved templates</div></div>
          <div className="arch-mcp"><b>MCP server</b> get_customer_360 · get_next_best_action · explain_decision · record_feedback. Consent is enforced inside the tool, not by the caller.</div></div>
        <div><div className="eyebrow">Used by</div><ul><li><b>Marketing</b> this console</li><li><b>Service agents</b> Customer 360° in the CRM</li><li><b>Channels</b> only after approval</li><li><b>Feedback</b> responses back to Bronze</li></ul></div>
      </div>
      <p className="method-text">The diagram above is a production target, not running infrastructure. Today the app uses FastAPI and SQLite; Databricks, live event processing, MCP and delivery are not implemented.</p>
    </Panel>

    <Panel title="Event replay" subtitle="What changes when new information arrives">{error ? <Loading error={error} /> : !r ? <Loading /> : <>
      <div className="metrics three"><Metric label="Source events" value={r.source_events} /><Metric label="Duplicates skipped" value={r.duplicates_skipped} /><Metric label="Decisions changed" value={r.changed} /></div>
      <p className="small-text muted">{r.note}</p>
      <div className="table-wrap"><table><thead><tr><th>Received</th><th>Customer</th><th>Event</th><th>Before → after</th></tr></thead><tbody>{r.changes.filter(c => c.changed).map(c => <tr key={c.event_id}><td>{c.ingested_at}</td><td>{c.customer_id}</td><td>{c.note}</td><td>{c.before} → {c.after}</td></tr>)}</tbody></table></div>
      <details><summary>Event types that never change a decision ({Object.values(r.unhandled_types).reduce((a, b) => a + b, 0)} events)</summary><ul className="ignored-events">{Object.entries(r.unhandled_types).map(([t, n]) => <li key={t}><b>{t.replaceAll('_', ' ')}</b> · {n}<span>{IGNORED[t] || 'Not used by this prototype.'}</span></li>)}</ul></details></>}
    </Panel>
  </>;
}
