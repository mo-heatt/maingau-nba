import {useState} from 'react';
import {useApi} from '../api';
import {Loading, Panel} from './ui';
import TimelineTrack, {entryId} from './TimelineTrack';

type Entry = {at: string; source: string; title: string; detail: string; flag: '' | 'bad' | 'warn' | 'good' | 'muted'; upcoming: boolean};
type Timeline = {customer_id: string; since: string | null; snapshot: string; entries: Entry[]; sources: {key: string; label: string; count: number}[]};

const PAGE = 40;
const date = (at: string) => new Date(at.replace(' ', 'T')).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});

// Every source system on one line, newest first, back to the day they became a customer.
export default function CustomerTimeline({id, revision}: {id: string; revision: number}) {
  const {data: t, error} = useApi<Timeline>('/customers/' + id + '/timeline', revision);
  const [source, setSource] = useState(''), [shown, setShown] = useState(PAGE);
  if (error) return <Loading error={error} />;
  if (!t) return <Loading />;
  const label = Object.fromEntries(t.sources.map(s => [s.key, s.label]));
  const items = t.entries.filter(e => !source || e.source === source);
  let year = '';
  return <Panel title="Customer timeline" subtitle={`Every system joined on ${t.customer_id}, from ${t.since ? date(t.since) : 'the first record'} to today · ${t.entries.length} entries`}>
    <TimelineTrack entries={t.entries} snapshot={t.snapshot} labels={label} />
    <div className="tl-filters" role="group" aria-label="Filter by source system">
      <button className={!source ? 'active' : ''} aria-pressed={!source} onClick={() => {setSource(''); setShown(PAGE);}}>All <span>{t.entries.length}</span></button>
      {t.sources.map(s => <button key={s.key} className={source === s.key ? 'active' : ''} aria-pressed={source === s.key} onClick={() => {setSource(s.key); setShown(PAGE);}}>{s.label} <span>{s.count}</span></button>)}
    </div>
    <ol className="tl">{items.slice(0, shown).map((e, i) => {
      const y = e.at.slice(0, 4), head = y !== year ? (year = y) : null;
      return <li key={i} id={entryId(e)} className={'tl-item tl-' + (e.flag || 'plain') + (e.upcoming ? ' tl-upcoming' : '')}>
        {head && <div className="tl-year">{head}</div>}
        <span className="tl-date">{date(e.at)}</span>
        <i className="tl-dot" aria-hidden="true" />
        <div className="tl-body">
          <span className={'tl-src tl-src-' + e.source}>{label[e.source] || e.source}</span>
          {e.upcoming && <span className="tl-src tl-next">Upcoming</span>}
          <b>{e.title}</b>
          {e.detail && <small>{e.detail}</small>}
        </div>
      </li>;
    })}</ol>
    {items.length > shown && <div className="show-more"><button className="button" onClick={() => setShown(n => n + PAGE)}>Show {Math.min(PAGE, items.length - shown)} older entries</button></div>}
    <p className="small-text muted tl-note">Long streams (charging, portal visits) show the latest entries only. Newsletter opens marked as Apple MPP are machine opens, not real reads. Live events come from the 1 Oct event stream, duplicates removed.</p>
  </Panel>;
}
