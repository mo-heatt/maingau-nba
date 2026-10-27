import {useState} from 'react';
import {Zap, PlugZap, Smartphone, Wifi, ShoppingCart, HousePlug, Check, ChevronDown, ExternalLink} from 'lucide-react';
import type {LucideIcon} from 'lucide-react';
import type {Customer} from '../types';
import {useApi, eur} from '../api';
import {categoryLink} from './productPresentation';
import ProductDetail from './ProductDetail';

type Item = {id: string; category: string; name: string; provider: string; status: string; source: string; source_ref: string; details: Record<string, unknown>; relationship: string; external: boolean};
const LINES: {key: string; label: string; what: string; Icon: LucideIcon; offerLines: string[]; categories: string[]}[] = [
  {key: 'energy', label: 'Energy', what: 'Electricity, gas, heat pump', Icon: Zap, offerLines: ['energy'], categories: ['electricity', 'gas']},
  {key: 'autostrom', label: 'Autostrom', what: 'Charging by app, card or chip', Icon: PlugZap, offerLines: ['e_mobility'], categories: ['charging']},
  {key: 'mobile', label: 'Mobile', what: 'Phone contracts', Icon: Smartphone, offerLines: ['mobile'], categories: ['mobile']},
  {key: 'internet', label: 'Internet', what: 'DSL and fibre', Icon: Wifi, offerLines: ['internet'], categories: ['internet']},
  {key: 'smart_living', label: 'Smart Living', what: 'HEMS, smart meter, smart home', Icon: HousePlug, offerLines: ['smart_living'], categories: ['devices']},
  {key: 'shop', label: 'Online shop', what: 'Wallboxes, solar, smart home', Icon: ShoppingCart, offerLines: ['shop'], categories: ['shop']},
];
const nice = (s: string) => s.replaceAll('_', ' ');
const date = (v: unknown) => typeof v === 'string' ? new Date(v.replace(' ', 'T')).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'}) : '';
const chips = (r: Record<string, unknown>) => {
  const out: string[] = [];
  if (typeof r.monthly_eur === 'number') out.push(eur(r.monthly_eur) + ' / month');
  if (typeof r.data_gb !== 'undefined') out.push(String(r.data_gb) + ' GB');
  if (typeof r.unit_eur_kwh === 'number') out.push(r.unit_eur_kwh.toLocaleString('de-DE', {maximumFractionDigits: 4}) + ' € / kWh');
  if (r.price_guarantee_until) out.push('guarantee until ' + date(r.price_guarantee_until));
  if (r.sim_count) out.push(r.sim_count + ' SIM');
  return out;
};

// Every MAINGAU business line at a glance. A line in use is a collapsible button: opening it
// reveals the products of that category; "Show all products" opens every line at once.
export default function BusinessLines({c, revision}: {c: Customer; revision: number}) {
  const {data} = useApi<{items: Item[]}>('/customers/' + c.id + '/products', revision);
  const items = data?.items || [];
  const shop = items.filter(i => i.category === 'shop' && !i.external);
  const offers = c.candidates.filter(k => !k.blocked.length && k.dclv > 0);
  const inUse = LINES.filter(l => l.key === 'shop' ? shop.length > 0 : c.products.some(p => p.line === l.key)).length;
  const [open, setOpen] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const [detail, setDetail] = useState<Item | null>(null);
  const toggle = (key: string) => {setAll(false);setOpen(cur => cur === key ? null : key)};
  const show = (key: string) => all || open === key;
  return <section className="lines">
    <div className="detail-section-heading">
      <h2>Business lines</h2>
      <div className="lines-tools">
        <span>{inUse} of {LINES.length} in use · grey: not in use yet</span>
        {inUse > 0 && <button className="button small" aria-pressed={all} onClick={() => {setOpen(null);setAll(v => !v)}}>{all ? 'Hide product lists' : 'Show all products'}</button>}
      </div>
    </div>
    <div className="lines-grid">{LINES.map(({key, label, what, Icon, offerLines, categories}) => {
      const held = key === 'shop' ? [] : c.products.filter(p => p.line === key);
      const lineItems = items.filter(i => categories.includes(i.category));
      const used = key === 'shop' ? shop.length > 0 : held.length > 0;
      const best = offers.filter(k => offerLines.includes(k.line || '')).sort((a, b) => b.dclv - a.dclv)[0];
      const expanded = used && show(key);
      const head = <><Icon size={20} aria-hidden="true" /><div><b>{label}</b><small>{what}</small></div>{used && <span className="line-ok" title="In use"><Check size={13} /></span>}{used && <ChevronDown size={16} className="line-chevron" aria-hidden="true" />}</>;
      return <article key={key} className={'line-card' + (used ? ' in-use' : '') + (expanded ? ' expanded' : '')}>
        {used
          ? <button type="button" className="line-head" aria-expanded={expanded} onClick={() => toggle(key)}>{head}</button>
          : <header className="line-head static">{head}</header>}
        {used && <ul className={'line-summary' + (expanded ? ' hidden' : '')}>{held.map((p, i) => {
          const r = p as unknown as Record<string, unknown>;
          const extra = r.price_guarantee_until ? `price guarantee until ${date(r.price_guarantee_until)}` : r.sim_count ? `${r.sim_count} SIM` : '';
          return <li key={i}><span>{p.name}</span><em className={p.status === 'active' || p.status === 'online' ? 'ok' : 'warn'}>{nice(p.status)}</em>{extra && <small>{extra}</small>}</li>;
        })}{used && key === 'shop' && <li><span>{shop.length} order{shop.length > 1 ? 's' : ''}</span><small>{shop.slice(0, 3).map(s => s.name).join(' · ')}</small></li>}</ul>}
        {expanded && <div className="line-products">
          {lineItems.map(item => {
            const link = categoryLink(item.category);
            return <div key={item.id} className="line-product">
              <div className="line-product-main">
                <b>{item.name}</b>
                <em className={item.status === 'active' || item.status === 'online' ? 'ok' : 'warn'}>{nice(item.status)}</em>
                {chips(item.details).map(chip => <small key={chip}>{chip}</small>)}
                {!item.external && item.relationship === 'purchase_record' && <small>purchase record</small>}
              </div>
              <div className="line-product-actions">
                <button className="button small" onClick={() => setDetail(item)}>Details</button>
                {!item.external && <a className="button small" href={link.url} target="_blank" rel="noreferrer" title={link.label + ' on maingau.de'}>{link.label}<ExternalLink size={11} /></a>}
              </div>
            </div>;
          })}
          {!lineItems.length && <p className="small-text muted">No verified product is recorded in this line yet.</p>}
        </div>}
        {!used && <p className="line-gap">Not in use{best ? <>. Best offer: <b>{best.name}</b> <span>+{eur(best.dclv)}</span></> : c.decision.action === 'service' ? '. No offer while a service case is open.' : '.'}</p>}
      </article>;
    })}</div>
    {detail && <ProductDetail cid={c.id} product={detail} onClose={() => setDetail(null)} />}
  </section>;
}
