import type {Customer} from '../types';
import {channel, eur} from '../api';

const pct = (p: number, d = 1) => (p * 100).toFixed(d).replace('.', ',') + ' %';
const signed = (v: number) => (v >= 0 ? '+' : '−') + eur(Math.abs(v));

// The top options the engine compared, with the calculation in one line, so "why this offer?" has a visible answer.
export default function BestOptions({c}: {c: Customer}) {
  const now = c.value.clv;
  const open = c.candidates.filter(k => !k.blocked.length).sort((a, b) => b.dclv - a.dclv);
  const top = open.slice(0, 5), blocked = c.candidates.length - open.length;
  if (!top.length) return null;
  return <section className="best-options">
    <div className="detail-section-heading"><h2>Best options for this customer</h2><span>Ranked by expected gain in customer value</span></div>
    <p className="best-formula">Expected gain = chance of yes × (value if yes − value today) + chance of no × (value if no − value today) − contact cost. Value today: <b>{eur(now)}</b>.</p>
    <ol>{top.map((k, i) => {
      const up = k.clv_accept - now, down = k.clv_reject - now;
      const cost = Math.max(0, k.p * up + (1 - k.p) * down - k.dclv);
      return <li key={k.offer} className={i === 0 ? 'is-pick' : ''}>
        <span className="best-rank">{i + 1}</span>
        <div className="best-main"><b>{k.name}</b>{i === 0 && <span className="best-tag">Engine's pick</span>}<small>{k.why} · {channel(k.channel)}</small>
          <code>{pct(k.p, 2)} × {signed(up)}{Math.abs(down) >= 0.05 ? ` + ${pct(1 - k.p, 2)} × ${signed(down)}` : ''}{cost >= 0.05 ? ` − ${eur(cost)}` : ''} = {signed(k.dclv)}</code></div>
        <div className="best-num"><span>Chance of yes</span><b>{pct(k.p)}</b></div>
        <div className="best-num"><span>Gain if yes</span><b>{signed(up)}</b></div>
        <div className="best-num total"><span>Expected gain</span><b>{signed(k.dclv)}</b></div>
      </li>;
    })}</ol>
    {blocked > 0 && <p className="best-foot">{blocked} more option{blocked > 1 ? 's were' : ' was'} blocked by the rules (already owned, no consent, open service case or not relevant). Full list: Insights → Engine alternatives & scoring.</p>}
  </section>;
}
