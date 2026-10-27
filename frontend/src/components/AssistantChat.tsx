import {Fragment, useEffect, useRef, useState} from 'react';
import type {KeyboardEvent} from 'react';
import {MessageCircle, X, ArrowUp, Sparkles} from 'lucide-react';
import {request} from '../api';
import '../assistant.css';

type Turn = {role: 'user' | 'assistant'; content: string; error?: boolean};

const SUGGESTIONS = ['Which offer is recommended most often?', 'Why is MG-100004 not getting an offer?', 'Which customers are stuck in service?'];

// Customer IDs in an answer become links to their profile; **text** becomes bold.
function Linked({text, onSelect}: {text: string; onSelect: (id: string) => void}) {
  return <>{text.split(/(\*\*[^*]+\*\*|MG-\d{6})/g).map((part, i) => /^MG-\d{6}$/.test(part)
    ? <button key={i} className="link" onClick={() => onSelect(part)}>{part}</button>
    : /^\*\*[^*]+\*\*$/.test(part) ? <b key={i}>{part.slice(2, -2)}</b>
    : <Fragment key={i}>{part}</Fragment>)}</>;
}

// The model answers in light markdown: bold headings on their own line, "- " or "1. " bullets, paragraphs.
function Answer({text, onSelect}: {text: string; onSelect: (id: string) => void}) {
  const blocks: {kind: 'p' | 'h' | 'ul' | 'ol'; lines: string[]}[] = [];
  for (const raw of text.split('\n')) {
    const line = raw.trim().replace(/^#{1,6}\s+/, '');
    if (!line) {blocks.push({kind: 'p', lines: []});continue}
    const bullet = line.match(/^[-*•]\s+(.*)/), numbered = line.match(/^\d+[.)]\s+(.*)/);
    const kind = bullet ? 'ul' : numbered ? 'ol' : /^\*\*[^*]+\*\*:?$/.test(line) ? 'h' : 'p';
    const content = bullet?.[1] ?? numbered?.[1] ?? (kind === 'h' ? line.replace(/^\*\*|\*\*:?$/g, '') : line);
    const last = blocks[blocks.length - 1];
    if (last && last.kind === kind && kind !== 'h' && last.lines.length) last.lines.push(content);
    else blocks.push({kind, lines: [content]});
  }
  return <>{blocks.filter(b => b.lines.length).map((b, i) =>
    b.kind === 'h' ? <h3 key={i}>{b.lines[0]}</h3>
    : b.kind === 'p' ? <p key={i}><Linked text={b.lines.join(' ')} onSelect={onSelect} /></p>
    : <b.kind key={i}>{b.lines.map((l, j) => <li key={j}><Linked text={l} onSelect={onSelect} /></li>)}</b.kind>)}</>;
}

// Floating data assistant: questions go to /assistant, which answers from the app's own numbers.
export default function AssistantChat({onSelect, onConnect}: {onSelect: (id: string) => void; onConnect: () => void}) {
  const [open, setOpen] = useState(false), [turns, setTurns] = useState<Turn[]>([]), [draft, setDraft] = useState(''), [busy, setBusy] = useState(false);
  const list = useRef<HTMLDivElement>(null), input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {if (open) input.current?.focus()}, [open]);
  useEffect(() => {if (list.current) list.current.scrollTop = list.current.scrollHeight}, [turns, busy]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    const history = [...turns.filter(t => !t.error), {role: 'user' as const, content: q}];
    setTurns(t => [...t, {role: 'user', content: q}]);setDraft('');setBusy(true);
    try {
      const r = await request<{answer: string}>('/assistant', 'POST', {messages: history.map(({role, content}) => ({role, content}))});
      setTurns(t => [...t, {role: 'assistant', content: r.answer}]);
    } catch (e) {
      setTurns(t => [...t, {role: 'assistant', content: (e as Error).message, error: true}]);
    } finally {setBusy(false)}
  }
  function keys(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {e.preventDefault();ask(draft)}
    if (e.key === 'Escape') setOpen(false);
  }

  return <>
    {open && <section className="assistant" role="dialog" aria-label="Data assistant">
      <header><Sparkles size={16} aria-hidden="true" /><h2>Data assistant</h2><button className="assistant-close" aria-label="Close assistant" onClick={() => setOpen(false)}><X size={16} /></button></header>
      <div className="assistant-list" ref={list} aria-live="polite">
        {!turns.length && <div className="assistant-empty"><p>Ask about customers, recommendations or service cases.</p>
          {SUGGESTIONS.map(s => <button key={s} className="assistant-suggestion" onClick={() => ask(s)}>{s}</button>)}</div>}
        {turns.map((t, i) => <div key={i} className={'assistant-msg from-' + t.role + (t.error ? ' error' : '')}>
          {t.role === 'assistant' && !t.error ? <Answer text={t.content} onSelect={onSelect} /> : t.content}
          {t.error && /Developer area/.test(t.content) && <button className="button small" onClick={onConnect}>Open Developer area</button>}
        </div>)}
        {busy && <div className="assistant-msg from-assistant thinking">Thinking…</div>}
      </div>
      <form className="assistant-input" onSubmit={e => {e.preventDefault();ask(draft)}}>
        <textarea ref={input} rows={1} value={draft} maxLength={2000} placeholder="Ask a question…" aria-label="Question" onChange={e => setDraft(e.target.value)} onKeyDown={keys} />
        <button type="submit" className="assistant-send" aria-label="Send" disabled={busy || !draft.trim()}><ArrowUp size={16} /></button>
      </form>
      <small className="assistant-note">AI answers from this app's mock data and can be wrong. Nothing is sent or changed.</small>
    </section>}
    <button className="assistant-fab" aria-label={open ? 'Close assistant' : 'Ask the data assistant'} aria-expanded={open} onClick={() => setOpen(v => !v)}>
      {open ? <X size={22} /> : <MessageCircle size={22} />}
    </button>
  </>;
}
