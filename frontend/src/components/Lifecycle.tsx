import {useState} from 'react';
import {BrainCircuit, LoaderCircle, Megaphone, RefreshCw} from 'lucide-react';
import {useApi, request, eur} from '../api';
import {STATIC_MODE} from '../staticApi';
import {Loading, Panel} from './ui';

const eur0 = (v: number) => new Intl.NumberFormat('de-DE', {style: 'currency', currency: 'EUR', maximumFractionDigits: 0}).format(v);

type Product = {product: string; line: string; source: string; adopters: number; median_age_days: number | null; new_90d: number; prior_90d: number; monthly_revenue_eur: number; undersized: number; oversized: number; misfit_share: number; guarantee_cliff_90d: number; cliff_share: number; fit_measure: string; holder_churn: number | null; stage: string; reasons: string[]};
type Opportunity = {product: string; line: string; stage: string; adopters: number; successor: string | null; contactable: number; blocked_or_not_ready: number; expected_gain_eur: number; mean_p: number};
type Cliff = {month: string; contracts: number; value_eur: number; tariffs: {tariff: string; contracts: number}[]};
type BriefItem = {product: string; action: string; observation: string; recommendation: string; expected_gain_eur: number; priority: 'now' | 'next' | 'later'};
type Brief = {headline: string; summary: string; recommendations: BriefItem[]; watchouts: string[]};
type BriefResult = {snapshot: string; source: 'ai' | 'catalogue-rules'; model: string | null; brief: Brief; note: string | null};
type View = {products: Product[]; opportunities: Opportunity[]; cliffs: Cliff[]; snapshot: string};
export type CampaignPrefill = {offer?: string; product?: string[]; name?: string};

const STAGE: Record<string, [string, string]> = {
  growing: ['Growing', 'stage-growing'], mature: ['Mature', 'stage-mature'],
  aging: ['Aging', 'stage-aging'], legacy: ['Legacy', 'stage-legacy'], dormant: ['Dormant', 'stage-dormant'],
};
const PRIORITY: Record<string, string> = {now: 'Do now', next: 'Next', later: 'Later'};

// Product lifecycle for marketing: deterministic portfolio health from contract data,
// an AI analyst brief grounded in those computed numbers, and migration campaigns
// whose euros come from the same engine scoring as everywhere else in the app.
export default function Lifecycle({revision, names, onNewCampaign}: {revision: number; names: Record<string, string>; onNewCampaign: (prefill: CampaignPrefill) => void}) {
  const {data, error} = useApi<View>('/marketing/lifecycle', revision);
  const [brief, setBrief] = useState<BriefResult | null>(null), [busy, setBusy] = useState(false), [failure, setFailure] = useState('');
  async function generate() {
    setBusy(true); setFailure('');
    try {setBrief(await request<BriefResult>('/marketing/lifecycle/brief', 'POST', {refresh: !!brief}))}
    catch (e) {setFailure((e as Error).message)} finally {setBusy(false)}
  }
  if (error) return <Loading error={error} />;
  if (!data) return <Loading />;
  const aging = data.products.filter(p => ['aging', 'legacy', 'dormant'].includes(p.stage));
  return <div className="lifecycle">
    <div className="mk-metrics">
      <Metric label="Products tracked" value={String(data.products.length)} hint="active plans and tariffs in the contracts" />
      <Metric label="Tired or worse" value={String(aging.length)} hint="aging, legacy or dormant products" />
      <Metric label="Computed migration gain" value={eur0(data.opportunities.reduce((s, o) => s + Math.max(0, o.expected_gain_eur), 0))} hint="expected CLV gain, engine-scored" />
      <Metric label="Guarantee cliff, 120 days" value={String(data.cliffs.reduce((s, c) => s + c.contracts, 0))} hint="energy contracts losing their price guarantee" />
    </div>
    <Panel title="Portfolio health" subtitle="Every product as a living offering · deterministic metrics from contract data">
      <div className="lc-grid">{data.products.map(p => {
        const [label, cls] = STAGE[p.stage] || [p.stage, ''];
        const trend = p.new_90d - p.prior_90d;
        const fit = p.undersized + p.oversized;
        return <article key={p.product + p.line} className={'lc-card ' + cls}>
          <header><div><b>{p.product}</b><small>{p.line.replaceAll('_', ' ')} · {p.adopters} holder{p.adopters === 1 ? '' : 's'} · {eur0(p.monthly_revenue_eur)}/mo</small></div><span className={'lc-stage ' + cls}>{label}</span></header>
          <div className="lc-signs">
            <span title="Median contract age">{p.median_age_days != null ? Math.round(p.median_age_days / 30) + ' mo' : '—'}<small>median age</small></span>
            <span className={trend > 0 ? 'up' : trend < 0 ? 'down' : ''}>{trend > 0 ? '+' : ''}{trend}<small>new 90d vs prior</small></span>
            {p.source === 'mobile_contracts'
              ? <span className={p.misfit_share >= .25 ? 'warn' : ''}>{p.undersized} / {p.oversized}<small>too tight / too wide</small></span>
              : <span className={p.guarantee_cliff_90d ? 'warn' : ''}>{p.guarantee_cliff_90d}<small>guarantee ends ≤90d</small></span>}
            <span>{p.holder_churn != null ? Math.round(p.holder_churn * 100) + '%' : '—'}<small>holder churn</small></span>
          </div>
          {fit > 0 && p.source === 'mobile_contracts' && <div className="lc-bar" title={`${p.fit_measure}: ${p.undersized} tight, ${p.oversized} wide of ${p.adopters}`}>
            <i className="tight" style={{width: (p.undersized / Math.max(1, p.adopters) * 100) + '%'}} />
            <i className="wide" style={{width: (p.oversized / Math.max(1, p.adopters) * 100) + '%'}} />
          </div>}
          <ul className="lc-reasons">{p.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </article>;
      })}</div>
    </Panel>
    <Panel title="Migration opportunities" subtitle="What the engine would already recommend to today's holders · same CLV math as the customer view">
      {data.opportunities.length ? <div className="table-wrap"><table className="lc-ops">
        <thead><tr><th>Product</th><th>Stage</th><th>Holders</th><th>Engine-ready successor</th><th>Contactable</th><th>Expected CLV gain</th><th aria-label="Create campaign" /></tr></thead>
        <tbody>{data.opportunities.map(o => <tr key={o.product + o.line}>
          <td><b>{o.product}</b><small>{o.line.replaceAll('_', ' ')}</small></td>
          <td><span className={'lc-stage ' + (STAGE[o.stage] || ['', ''])[1]}>{(STAGE[o.stage] || [o.stage])[0]}</span></td>
          <td>{o.adopters}</td>
          <td>{o.successor ? <b>{names[o.successor] || o.successor}</b> : <span className="muted">no positive candidate</span>}{o.successor && <small>≈{(o.mean_p * 100).toFixed(1).replace('.', ',')}% yes</small>}</td>
          <td>{o.contactable}<small>{o.blocked_or_not_ready} not ready</small></td>
          <td className={o.expected_gain_eur > 0 ? 'gain' : ''}>{o.expected_gain_eur > 0 ? '+' : ''}{eur(o.expected_gain_eur)}</td>
          <td>{o.successor && o.expected_gain_eur > 0 && !STATIC_MODE && <button className="button small" title={`Campaign: ${names[o.successor] || o.successor} for ${o.product} holders`} onClick={() => onNewCampaign({offer: o.successor!, product: [o.product], name: `${o.product} refresh`})}><Megaphone size={12} />Campaign</button>}</td>
        </tr>)}</tbody>
      </table></div>
        : <p className="muted small-text">No computed migration opportunity right now.</p>}
      <p className="small-text muted">Expected gain = Σ p(accept) × (CLV after − CLV now) − contact cost over today's holders, computed by the decision engine. Campaigns still pass consent, exclusions and contact limits.</p>
    </Panel>
    {data.cliffs.length > 0 && <Panel title="Price-guarantee cliff" subtitle="Renewal waves need retention actions before the tariff ends, not after">
      <div className="lc-cliffs">{data.cliffs.map(c => <div key={c.month} className="lc-cliff">
        <b>{new Date(c.month + '-01T12:00:00').toLocaleDateString('en-GB', {month: 'long', year: 'numeric'})}</b>
        <span>{c.contracts} contract{c.contracts === 1 ? '' : 's'} · {eur0(c.value_eur)} annual volume</span>
        <small>{c.tariffs.slice(0, 3).map(t => `${t.tariff} (${t.contracts})`).join(' · ')}{c.tariffs.length > 3 ? ' · …' : ''}</small>
      </div>)}</div>
    </Panel>}
    <Panel title="AI portfolio analyst" subtitle="Interprets the computed metrics · it cannot invent products or euros">
      {failure && <p className="ai-warning">{failure}</p>}
      {!brief && !busy && <div className="lc-brief-empty">
        <p className="muted">The analyst reads the portfolio health, migration opportunities and guarantee cliffs above, then proposes concrete actions with the computed euro figures.</p>
        <button className="button primary" disabled={STATIC_MODE} onClick={generate}><BrainCircuit size={15} />Generate portfolio brief</button>
      </div>}
      {busy && <p className="muted"><LoaderCircle size={14} className="loading-spin" /> The analyst is reading the portfolio…</p>}
      {brief && !busy && <div className="lc-brief">
        <header><div><span className="eyebrow">{brief.source === 'ai' ? 'AI ANALYST · ' + (brief.model || '') : 'COMPUTED SUMMARY'}</span><h3>{brief.brief.headline}</h3></div>
          <button className="button small" onClick={generate} disabled={busy}><RefreshCw size={12} />Rethink</button></header>
        <p className="lc-summary">{brief.brief.summary}</p>
        <ol className="lc-recs">{brief.brief.recommendations.map((r, i) => <li key={i} className={'lc-rec lc-' + r.priority}>
          <div className="lc-rec-head"><b>{r.product}</b><span className="lc-action">{r.action}</span><span className="lc-priority">{PRIORITY[r.priority] || r.priority}</span>{r.expected_gain_eur > 0 && <span className="lc-euros">+{eur0(r.expected_gain_eur)} expected CLV gain</span>}</div>
          <p><b>Seen in data:</b> {r.observation}</p>
          <p><b>Recommendation:</b> {r.recommendation}</p>
        </li>)}</ol>
        {brief.brief.watchouts.length > 0 && <div className="lc-watch"><b>Watchouts</b><ul>{brief.brief.watchouts.map((w, i) => <li key={i}>{w}</li>)}</ul></div>}
        {brief.note && <p className="small-text muted">{brief.note}</p>}
      </div>}
    </Panel>
  </div>;
}

function Metric({label, value, hint}: {label: string; value: string; hint?: string}) {
  return <div className="mk-metric"><span>{label}</span><strong>{value}</strong>{hint && <small>{hint}</small>}</div>;
}
