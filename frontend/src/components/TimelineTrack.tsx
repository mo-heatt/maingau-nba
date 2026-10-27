import {useRef, useState} from 'react';
import type {KeyboardEvent, MouseEvent} from 'react';

// One line from the first record to today: every contact, contract and problem as a dot.
// Hovering anywhere on the line shows the nearest event(s); clicking jumps to it in the list.
type Entry = {at: string; source: string; title: string; detail: string; flag: string; upcoming: boolean};

const t = (at: string) => new Date(at.replace(' ', 'T')).getTime();
const kind = (e: Entry) =>
  e.source === 'crm' || (e.source === 'contract' && / started$/.test(e.title)) ? 'contract'
    : e.flag === 'bad' ? 'problem'
    : e.flag === 'good' ? 'good'
    : e.flag === 'warn' || e.upcoming ? 'deadline'
    : 'other';
const LEGEND: [string, string][] = [['contract', 'Customer or contract start'], ['problem', 'Problem'], ['good', 'Positive response'], ['deadline', 'Deadline'], ['other', 'Other contact']];
const day = (at: string) => new Date(at.replace(' ', 'T')).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});
export const entryId = (e: Entry) => 'tl-' + (e.at + e.title).replace(/[^a-zA-Z0-9]/g, '');

const W = 1000, L = 14, R = 986, Y = 46, NEAR = W, CLUSTER = 7, MAX_SHOWN = 4;

export default function TimelineTrack({entries, snapshot, labels: sourceLabel}: {entries: Entry[]; snapshot: string; labels: Record<string, string>}) {
  const svg = useRef<SVGSVGElement>(null);
  const [focus, setFocus] = useState<number | null>(null);
  if (entries.length < 2) return null;
  const start = Math.min(...entries.map(e => t(e.at))), today = t(snapshot);
  const end = Math.max(today, ...entries.map(e => t(e.at)));
  const x = (ms: number) => L + ((ms - start) / Math.max(1, end - start)) * (R - L);
  const points = entries.map((e, i) => ({i, e, px: x(t(e.at)), k: kind(e)})).sort((a, b) => a.px - b.px);
  const years: number[] = [];
  for (let y = new Date(start).getFullYear() + 1; y <= new Date(end).getFullYear(); y++) years.push(y);
  const step = Math.max(1, Math.ceil(years.length / 8));
  // Labels for milestones only, on two rows, skipped when they would overlap.
  const lastX = [-999, -999];
  const labels = points.filter(p => p.k === 'contract').map(p => {
    const row = p.px - lastX[0] > 150 ? 0 : p.px - lastX[1] > 150 ? 1 : -1;
    if (row < 0) return null;
    lastX[row] = p.px;
    const text = p.e.source === 'crm' ? 'Became a customer' : p.e.title.replace(/ started$/, '');
    return {px: p.px, row, text};
  }).filter(Boolean) as {px: number; row: number; text: string}[];

  // The hovered point plus everything that sits on top of it.
  const active = focus === null ? [] : (() => {
    const centre = points[focus].px;
    return points.filter(p => Math.abs(p.px - centre) <= CLUSTER).sort((a, b) => b.e.at.localeCompare(a.e.at));
  })();
  const activeIdx = new Set(active.map(p => p.i));

  function nearest(clientX: number) {
    const box = svg.current?.getBoundingClientRect();
    if (!box) return null;
    const sx = ((clientX - box.left) / box.width) * W;
    let best = -1, dist = Infinity;
    points.forEach((p, n) => { const d = Math.abs(p.px - sx); if (d < dist) { dist = d; best = n; } });
    return dist <= NEAR ? best : null;
  }
  const move = (ev: MouseEvent<SVGSVGElement>) => setFocus(nearest(ev.clientX));
  const jump = () => {
    if (!active.length) return;
    const el = document.getElementById(entryId(active[0].e));
    if (el) { el.scrollIntoView({behavior: 'smooth', block: 'center'}); el.classList.add('tl-flash'); setTimeout(() => el.classList.remove('tl-flash'), 1600); }
  };
  const keys = (ev: KeyboardEvent<SVGSVGElement>) => {
    if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') {
      ev.preventDefault();
      setFocus(f => f === null ? (ev.key === 'ArrowRight' ? 0 : points.length - 1) : Math.min(points.length - 1, Math.max(0, f + (ev.key === 'ArrowRight' ? 1 : -1))));
    } else if (ev.key === 'Enter') jump();
    else if (ev.key === 'Escape') setFocus(null);
  };
  const tipX = active.length ? (active[0].px / W) * 100 : 0;

  return <div className="tt">
    <div className="tt-stage">
      <svg ref={svg} viewBox={`0 0 ${W} 92`} role="img" tabIndex={0}
        aria-label={`${entries.length} entries from ${new Date(start).getFullYear()} to today. Use the arrow keys to step through them.`}
        onMouseMove={move} onMouseLeave={() => setFocus(null)} onClick={jump} onKeyDown={keys} onBlur={() => setFocus(null)}
        className={active.length ? 'is-hovering' : ''}>
        <rect x={0} y={20} width={W} height={52} className="tt-hit" />
        <line x1={L} x2={x(today)} y1={Y} y2={Y} className="tt-axis" />
        {end > today && <line x1={x(today)} x2={R} y1={Y} y2={Y} className="tt-axis future" />}
        {years.filter((_, i) => i % step === 0).map(y => { const px = x(new Date(`${y}-01-01`).getTime()); return <g key={y}><line x1={px} x2={px} y1={Y - 4} y2={Y + 4} className="tt-tick" /><text x={px} y={Y + 20} textAnchor="middle" className="tt-year">{y}</text></g>; })}
        {labels.map((l, i) => <text key={i} x={Math.min(Math.max(l.px, 60), W - 60)} y={l.row ? 12 : 26} textAnchor="middle" className="tt-label">{l.text}</text>)}
        {[...points].sort((a, b) => (a.k === 'other' ? -1 : 0) - (b.k === 'other' ? -1 : 0)).map(p => {
          const on = activeIdx.has(p.i), r = (p.k === 'other' ? 3.5 : 5) + (on ? 2.5 : 0);
          return p.k === 'contract'
            ? <rect key={p.i} x={p.px - r} y={Y - r} width={r * 2} height={r * 2} className={'tt-dot tt-contract' + (on ? ' on' : '')} />
            : <circle key={p.i} cx={p.px} cy={Y} r={r} className={'tt-dot tt-' + p.k + (on ? ' on' : '')} />;
        })}
        <line x1={x(today)} x2={x(today)} y1={Y - 12} y2={Y + 12} className="tt-today" />
        <text x={Math.min(x(today), W - 24)} y={Y + 34} textAnchor="middle" className="tt-today-label">Today</text>
        {active.length > 0 && <line x1={active[0].px} x2={active[0].px} y1={Y - 16} y2={Y + 16} className="tt-cursor" />}
      </svg>
      {active.length > 0 && <div className="tt-tip" role="status" style={{left: `clamp(150px, ${tipX}%, calc(100% - 150px))`}}>
        {active.slice(0, MAX_SHOWN).map(p => <div key={p.i} className={'tt-tip-row tt-' + p.k}>
          <div className="tt-tip-head"><i className={'tt-key tt-' + p.k} /><span>{day(p.e.at)}</span><em>{sourceLabel[p.e.source] || p.e.source}</em>{p.e.upcoming && <em className="next">Upcoming</em>}</div>
          <b>{p.e.title}</b>
          {p.e.detail && <small>{p.e.detail.length > 140 ? p.e.detail.slice(0, 139) + '…' : p.e.detail}</small>}
        </div>)}
        {active.length > MAX_SHOWN && <p className="tt-more">+{active.length - MAX_SHOWN} more around this date</p>}
        <p className="tt-hint">Click to jump to it in the list</p>
      </div>}
    </div>
    <div className="tt-legend">{LEGEND.map(([k, label]) => <span key={k}><i className={'tt-key tt-' + k} />{label}</span>)}<span className="tt-legend-hint">Hover the line for details</span></div>
  </div>;
}
