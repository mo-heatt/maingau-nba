import {useEffect, useRef, useState} from 'react';
import type {DragEvent} from 'react';
import {UserPlus, FileUp, FileDown, X, CheckCircle2, AlertTriangle} from 'lucide-react';
import {request} from '../api';
import {STATIC_MODE} from '../staticApi';

// One customer per file: master data and contact consents, from CSV or JSON.
const CONSENTS = ['newsletter_email', 'marketing_email', 'marketing_phone', 'marketing_sms', 'portal_app_personalisation', 'profiling_analytics'];
const MASTER = ['customer_id', 'customer_type', 'customer_since', 'birth_year', 'postal_code_prefix', 'city', 'household_size', 'portal_account', 'app_installed', 'preferred_contact_language'];
const CONSENT_LABEL: Record<string, string> = {newsletter_email: 'Newsletter e-mail', marketing_email: 'Marketing e-mail', marketing_phone: 'Phone', marketing_sms: 'SMS', portal_app_personalisation: 'Portal & app personalisation', profiling_analytics: 'Profiling & analytics'};

type Payload = {customer: Record<string, unknown>; consents: Record<string, string>};
type Preview = {customer: Record<string, unknown>; consents: Record<string, string>; defaulted: string[]; stored: boolean};

function example(id: string): Payload {
  return {customer: {customer_id: id, customer_type: 'B2C', customer_since: '2026-09-15', birth_year: 1988, postal_code_prefix: '603', city: 'Frankfurt am Main', household_size: 2, portal_account: true, app_installed: false, preferred_contact_language: 'de'},
    consents: {newsletter_email: 'granted', marketing_email: 'granted', marketing_phone: 'not_given', marketing_sms: 'not_given', portal_app_personalisation: 'granted', profiling_analytics: 'not_given'}};
}

// CSV: a header row and one data row; comma or semicolon (German Excel) both work. Consent columns are consent_<type>.
function parseCsv(text: string): Payload {
  const lines = text.replace(/^﻿/, '').split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) throw Error('The CSV needs a header row and one customer row.');
  if (lines.length > 2) throw Error('One customer per file: the CSV has more than one data row.');
  const sep = (lines[0].match(/;/g) || []).length > (lines[0].match(/,/g) || []).length ? ';' : ',';
  const split = (line: string) => {
    const out: string[] = []; let cur = '', quoted = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') { if (quoted && line[i + 1] === '"') { cur += '"'; i++; } else quoted = !quoted; }
      else if (ch === sep && !quoted) { out.push(cur); cur = ''; }
      else cur += ch;
    }
    out.push(cur); return out.map(v => v.trim());
  };
  const head = split(lines[0]).map(h => h.toLowerCase()), row = split(lines[1]);
  const customer: Record<string, unknown> = {}, consents: Record<string, string> = {};
  head.forEach((h, i) => {
    const v = row[i] ?? '';
    if (v === '') return;
    if (h.startsWith('consent_')) consents[h.slice(8)] = v.toLowerCase();
    else customer[h] = /^(true|yes|ja|1)$/i.test(v) && ['portal_account', 'app_installed'].includes(h) ? true
      : /^(false|no|nein|0)$/i.test(v) && ['portal_account', 'app_installed'].includes(h) ? false
      : ['birth_year', 'household_size'].includes(h) && /^\d+$/.test(v) ? Number(v) : v;
  });
  return {customer, consents};
}

function parseJson(text: string): Payload {
  const d = JSON.parse(text);
  if (Array.isArray(d)) throw Error('One customer per file: the JSON contains a list.');
  if (d.customer) return {customer: d.customer, consents: d.consents || {}};
  const customer: Record<string, unknown> = {}, consents: Record<string, string> = {...(d.consents || {})};
  Object.entries(d).forEach(([k, v]) => { if (k.startsWith('consent_')) consents[k.slice(8)] = String(v); else if (k !== 'consents') customer[k] = v; });
  return {customer, consents};
}

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function CustomerImport({ids, onImported}: {ids: string[]; onImported: (id: string) => void}) {
  const modal = useRef<HTMLDialogElement>(null), input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false), [file, setFile] = useState(''), [payload, setPayload] = useState<Payload | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [drag, setDrag] = useState(false);
  const next = 'MG-' + String(Math.max(100000, ...ids.map(i => Number(i.slice(3)) || 0)) + 1).padStart(6, '0');

  useEffect(() => { const d = modal.current; if (!d) return; if (open && !d.open) d.showModal(); if (!open && d.open) d.close(); }, [open]);
  function reset() { setFile(''); setPayload(null); setPreview(null); setError(''); if (input.current) input.current.value = ''; }
  function close() { setOpen(false); reset(); }

  async function read(f: File) {
    reset(); setFile(f.name);
    if (f.size > 200_000) { setError('The file is too large for one customer (max 200 KB).'); return; }
    try {
      const text = await f.text();
      const p = /\.json$/i.test(f.name) || text.trim().startsWith('{') ? parseJson(text) : parseCsv(text);
      setPayload(p);
      if (STATIC_MODE) { setError('This online demo is read-only. Import works in the full app.'); return; }
      setBusy(true);
      setPreview(await request<Preview>('/customers/import', 'POST', {...p, dry_run: true}));  // validate only, nothing stored
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function create() {
    if (!payload) return;
    setBusy(true); setError('');
    try {
      const r = await request<Preview>('/customers/import', 'POST', payload);
      const id = String(r.customer.customer_id); close(); onImported(id);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  const drop = (e: DragEvent) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) read(f); };
  const ex = example(next);
  const csv = [...MASTER, ...CONSENTS.map(c => 'consent_' + c)].join(',') + '\n' + [...MASTER.map(k => String(ex.customer[k])), ...CONSENTS.map(c => ex.consents[c])].join(',') + '\n';

  return <>
    <button className="button import-trigger" onClick={() => setOpen(true)}><UserPlus size={15} />Import customer</button>
    <dialog ref={modal} className="import-dialog" aria-labelledby="import-title" onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === modal.current) close(); }}>
      <header className="import-head">
        <UserPlus size={26} aria-hidden="true" />
        <div><h2 id="import-title">Import a customer</h2><p>One customer per file · master data and contact consents.</p></div>
        <button className="button import-close" aria-label="Close" onClick={close}><X size={18} /></button>
      </header>
      <div className="import-body">
        <label className={'import-drop' + (drag ? ' is-drag' : '') + (file ? ' has-file' : '')} onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={drop}>
          <input ref={input} type="file" accept=".csv,.json,text/csv,application/json" onChange={e => { const f = e.target.files?.[0]; if (f) read(f); }} />
          <FileUp size={30} aria-hidden="true" />
          <b>{file || 'Choose a CSV or JSON file'}</b>
          <span>{file ? (busy ? 'Checking…' : 'Choose another file or drop it here.') : 'Or drop it here. Nothing is stored until you confirm.'}</span>
        </label>
        {error && <p className="import-error" role="alert"><AlertTriangle size={16} />{error}</p>}
        {preview && <div className="import-preview">
          <div className="import-preview-title"><CheckCircle2 size={16} />Ready to import <b>{String(preview.customer.customer_id)}</b></div>
          <dl>
            <div><dt>City</dt><dd>{String(preview.customer.city)} ({String(preview.customer.postal_code_prefix).padStart(3, '0')}xx)</dd></div>
            <div><dt>Customer since</dt><dd>{String(preview.customer.customer_since)}</dd></div>
            <div><dt>Type · household</dt><dd>{String(preview.customer.customer_type)} · {String(preview.customer.household_size)}</dd></div>
            <div><dt>Language</dt><dd>{String(preview.customer.preferred_contact_language).toUpperCase()}</dd></div>
          </dl>
          <ul className="import-consents">{CONSENTS.map(c => <li key={c} className={preview.consents[c] === 'granted' ? 'ok' : ''}><span>{CONSENT_LABEL[c]}</span><em>{preview.consents[c].replace('_', ' ')}{preview.defaulted.includes(c) ? ' · not in file' : ''}</em></li>)}</ul>
          {preview.defaulted.length > 0 && <p className="import-note">Consents missing from the file are stored as “not given”. No consent is ever assumed.</p>}
        </div>}
        <p className="import-format">Need the format?
          <button className="link" onClick={() => download('customer-import-template.csv', csv, 'text/csv')}><FileDown size={15} />CSV template</button>
          <button className="link" onClick={() => download('customer-import-template.json', JSON.stringify(ex, null, 2) + '\n', 'application/json')}><FileDown size={15} />JSON template</button>
        </p>
        <div className="import-actions">
          <button className="button primary" disabled={!preview || busy || STATIC_MODE} onClick={create}><CheckCircle2 size={16} />{busy && preview ? 'Creating…' : 'Create customer'}</button>
          <button className="button" onClick={close}>Cancel</button>
        </div>
        <p className="import-foot">Imported rows are added next to the source data and can’t be changed or deleted afterwards. Every import is written to the audit log.</p>
      </div>
    </dialog>
  </>;
}
