// One line from the first record to today: every contact, contract and problem as a dot.
type Entry = {at: string; source: string; title: string; flag: string; upcoming: boolean};

const t = (at: string) => new Date(at.replace(' ', 'T')).getTime();
const kind = (e: Entry) =>
  e.source === 'crm' || (e.source === 'contract' && / started$/.test(e.title)) ? 'contract'
    : e.flag === 'bad' ? 'problem'
    : e.flag === 'good' ? 'good'
    : e.flag === 'warn' || e.upcoming ? 'deadline'
    : 'other';
const LEGEND: [string, string][] = [['contract', 'Customer or contract start'], ['problem', 'Problem'], ['good', 'Positive response'], ['deadline', 'Deadline'], ['other', 'Other contact']];

export default function TimelineTrack({entries, snapshot}: {entries: Entry[]; snapshot: string}) {
  if (entries.length < 2) return null;
  const W = 1000, L = 14, R = 986, Y = 46;
  const start = Math.min(...entries.map(e => t(e.at))), today = t(snapshot);
  const end = Math.max(today, ...entries.map(e => t(e.at)));
  const x = (ms: number) => L + ((ms - start) / Math.max(1, end - start)) * (R - L);
  const years: number[] = [];
  for (let y = new Date(start).getFullYear() + 1; y <= new Date(end).getFullYear(); y++) years.push(y);
  const step = Math.max(1, Math.ceil(years.length / 8));
  // Labels for milestones only, on two rows, skipped when they would overlap.
  const lastX = [-999, -999];
  const labels = [...entries].reverse().filter(e => kind(e) === 'contract').map(e => {
    const px = x(t(e.at)), row = px - lastX[0] > 150 ? 0 : px - lastX[1] > 150 ? 1 : -1;
    if (row < 0) return null;
    lastX[row] = px;
    const text = e.source === 'crm' ? 'Became a customer' : e.title.replace(/ started$/, '').replace(/ \((electricity|gas)\)/, ' ($1)');
    return {px, row, text};
  }).filter(Boolean) as {px: number; row: number; text: string}[];
  const dots = [...entries].sort((a, b) => (kind(a) === 'other' ? -1 : 0) - (kind(b) === 'other' ? -1 : 0));
  return <div className="tt">
    <svg viewBox={`0 0 ${W} 92`} role="img" aria-label={`${entries.length} entries from ${new Date(start).getFullYear()} to today`}>
      <line x1={L} x2={x(today)} y1={Y} y2={Y} className="tt-axis" />
      {end > today && <line x1={x(today)} x2={R} y1={Y} y2={Y} className="tt-axis future" />}
      {years.filter((_, i) => i % step === 0).map(y => { const px = x(new Date(`${y}-01-01`).getTime()); return <g key={y}><line x1={px} x2={px} y1={Y - 4} y2={Y + 4} className="tt-tick" /><text x={px} y={Y + 20} textAnchor="middle" className="tt-year">{y}</text></g>; })}
      {labels.map((l, i) => <text key={i} x={Math.min(Math.max(l.px, 60), W - 60)} y={l.row ? 12 : 26} textAnchor="middle" className="tt-label">{l.text}</text>)}
      {dots.map((e, i) => { const k = kind(e), px = x(t(e.at));
        return k === 'contract'
          ? <rect key={i} x={px - 5} y={Y - 5} width={10} height={10} className="tt-dot tt-contract"><title>{e.at.slice(0, 10)} · {e.title}</title></rect>
          : <circle key={i} cx={px} cy={Y} r={k === 'other' ? 3.5 : 5} className={'tt-dot tt-' + k}><title>{e.at.slice(0, 10)} · {e.title}</title></circle>; })}
      <line x1={x(today)} x2={x(today)} y1={Y - 12} y2={Y + 12} className="tt-today" />
      <text x={Math.min(x(today), W - 24)} y={Y + 34} textAnchor="middle" className="tt-today-label">Today</text>
    </svg>
    <div className="tt-legend">{LEGEND.map(([k, label]) => <span key={k}><i className={'tt-key tt-' + k} />{label}</span>)}</div>
  </div>;
}
