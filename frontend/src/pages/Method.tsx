import {useApi} from '../api';
import type {Replay} from '../types';
import {Metric, PageTitle, Panel, Loading} from '../components/ui';

// The team's seven steps, in the words we use in the pitch.
const steps: [string, string, string][] = [
  ['1', 'Profile', 'Everything about one customer in one row: products, value, problems, consent, behaviour, how they write. Late records are filtered at the snapshot.'],
  ['2', 'When', 'Every night for all customers, and right away for one customer when an event arrives: a complaint, a consent change, an unpaid bill, a purchase.'],
  ['3', 'Rules', 'Complaint or unpaid bill: fix, don’t sell. Cancellation: a person decides. No consent: channel removed. Already owned or contacted too often: skip.'],
  ['4', 'Best offer', 'Every allowed offer gets a value: chance of yes × what Maingau earns − cost. The highest wins; if nothing is worth a contact, do nothing.'],
  ['5', 'Channel & tone', 'Only channels with consent, where the customer will see it soon (3+ portal logins in 90 days for a pop-up). Du or Sie from their own words.'],
  ['6', 'Message', 'Approved German template for the offer and tone. AI drafts stay inside it: no new prices, no pressure.'],
  ['7', 'Approve & send', 'Marketing approves each decision version. A stable 10% control group is logged but never contacted.'],
];

export default function Method({revision}: {revision: number}) {
  const {data: r, error} = useApi<Replay>('/replay', revision);
  return <>
    <PageTitle eyebrow="How it works" title="Sell when it helps, fix when it hurts." />
    <p className="page-intro">One engine on the server; every screen shows the same result. Seven steps per customer, and an eighth that learns from the results.</p>
    <div className="ov-steps method-steps">{steps.map(([n, title, text]) => <div key={n}><span>{n}</span><h3>{title}</h3><p>{text}</p></div>)}</div>
    <div className="notice learn-note"><b>8 · Learn.</b> After two weeks we compare customers we contacted with the 1 in 10 we held back. The difference (uplift) is what the contact really caused; it updates the chance of yes for that offer, channel and tone.</div>

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
      <p className="method-text">Today this prototype runs the same engine on FastAPI with SQLite; the tables map one to one onto the Delta tables above.</p>
    </Panel>

    <Panel title="Event replay" subtitle="What changes when new information arrives">{error ? <Loading error={error} /> : !r ? <Loading /> : <>
      <div className="metrics three"><Metric label="Source events" value={r.source_events} /><Metric label="Duplicates skipped" value={r.duplicates_skipped} /><Metric label="Decisions changed" value={r.changed} /></div>
      <p className="small-text muted">{r.note}</p>
      <div className="table-wrap"><table><thead><tr><th>Received</th><th>Customer</th><th>Event</th><th>Before → after</th></tr></thead><tbody>{r.changes.filter(c => c.changed).map(c => <tr key={c.event_id}><td>{c.ingested_at}</td><td>{c.customer_id}</td><td>{c.note}</td><td>{c.before} → {c.after}</td></tr>)}</tbody></table></div>
      <details><summary>Event types not handled by this prototype</summary><pre>{JSON.stringify(r.unhandled_types, null, 2)}</pre></details></>}
    </Panel>
  </>;
}
