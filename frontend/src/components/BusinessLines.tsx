import {Zap, PlugZap, Smartphone, Wifi, ShoppingCart, HousePlug, Check} from 'lucide-react';
import type {LucideIcon} from 'lucide-react';
import type {Customer} from '../types';
import {useApi, eur} from '../api';

type Item = {category: string; name: string; status: string; details: Record<string, unknown>; external: boolean};
const LINES: {key: string; label: string; what: string; Icon: LucideIcon; offerLines: string[]}[] = [
  {key: 'energy', label: 'Energy', what: 'Electricity, gas, heat pump', Icon: Zap, offerLines: ['energy']},
  {key: 'autostrom', label: 'Autostrom', what: 'Charging by app, card or chip', Icon: PlugZap, offerLines: ['e_mobility']},
  {key: 'mobile', label: 'Mobile', what: 'Phone contracts', Icon: Smartphone, offerLines: ['mobile']},
  {key: 'internet', label: 'Internet', what: 'DSL and fibre', Icon: Wifi, offerLines: ['internet']},
  {key: 'smart_living', label: 'Smart Living', what: 'HEMS, smart meter, smart home', Icon: HousePlug, offerLines: ['smart_living']},
  {key: 'shop', label: 'Online shop', what: 'Wallboxes, solar, smart home', Icon: ShoppingCart, offerLines: ['shop']},
];
const nice = (s: string) => s.replaceAll('_', ' ');
const date = (v: unknown) => typeof v === 'string' ? new Date(v.replace(' ', 'T')).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'}) : '';

// Every MAINGAU business line at a glance: in use, or greyed out with the best open offer for it.
export default function BusinessLines({c, revision}: {c: Customer; revision: number}) {
  const {data} = useApi<{items: Item[]}>('/customers/' + c.id + '/products', revision);
  const shop = (data?.items || []).filter(i => i.category === 'shop' && !i.external);
  const offers = c.candidates.filter(k => !k.blocked.length && k.dclv > 0);
  const inUse = LINES.filter(l => l.key === 'shop' ? shop.length > 0 : c.products.some(p => p.line === l.key)).length;
  return <section className="lines">
    <div className="detail-section-heading"><h2>Business lines</h2><span>{inUse} of {LINES.length} in use · grey: not in use yet</span></div>
    <div className="lines-grid">{LINES.map(({key, label, what, Icon, offerLines}) => {
      const held = key === 'shop' ? [] : c.products.filter(p => p.line === key);
      const used = key === 'shop' ? shop.length > 0 : held.length > 0;
      const best = offers.filter(k => offerLines.includes(k.line || '')).sort((a, b) => b.dclv - a.dclv)[0];
      return <article key={key} className={'line-card' + (used ? ' in-use' : '')}>
        <header><Icon size={20} aria-hidden="true" /><div><b>{label}</b><small>{what}</small></div>{used && <span className="line-ok" title="In use"><Check size={13} /></span>}</header>
        {used && key !== 'shop' && <ul>{held.map((p, i) => {
          const r = p as unknown as Record<string, unknown>;
          const extra = r.price_guarantee_until ? `price guarantee until ${date(r.price_guarantee_until)}` : r.sim_count ? `${r.sim_count} SIM` : '';
          return <li key={i}><span>{p.name}</span><em className={p.status === 'active' || p.status === 'online' ? 'ok' : 'warn'}>{nice(p.status)}</em>{extra && <small>{extra}</small>}</li>;
        })}</ul>}
        {used && key === 'shop' && <ul><li><span>{shop.length} order{shop.length > 1 ? 's' : ''}</span><small>{shop.slice(0, 3).map(s => s.name).join(' · ')}</small></li></ul>}
        {!used && <p className="line-gap">Not in use{best ? <>. Best offer: <b>{best.name}</b> <span>+{eur(best.dclv)}</span></> : c.decision.action === 'service' ? '. No offer while a service case is open.' : '.'}</p>}
      </article>;
    })}</div>
  </section>;
}
