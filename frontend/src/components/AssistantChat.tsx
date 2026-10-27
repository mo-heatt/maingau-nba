import {Fragment, useEffect, useRef, useState} from 'react';
import type {KeyboardEvent} from 'react';
import {MessageCircle, X, ArrowUp, Sparkles} from 'lucide-react';
import {request} from '../api';
import '../assistant.css';

type Turn = {role: 'user' | 'assistant'; content: string; error?: boolean};

const SUGGESTIONS = ['Which offer is recommended most often?', 'Why is MG-100004 not getting an offer?', 'Which customers are stuck in service?'];

// Customer IDs in an answer become links to their profile.
function Linked({text, onSelect}: {text: string; onSelect: (id: string) => void}) {
  return <>{text.split(/(MG-\d{6})/g).map((part, i) => /^MG-\d{6}$/.test(part)
    ? <button key={i} className="link" onClick={() => onSelect(part)}>{part}</button>
    : <Fragment key={i}>{part}</Fragment>)}</>;
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
          {t.role === 'assistant' && !t.error ? <Linked text={t.content} onSelect={onSelect} /> : t.content}
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
