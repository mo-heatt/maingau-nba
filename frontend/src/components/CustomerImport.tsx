import {useEffect,useRef,useState} from 'react';
import {AlertTriangle,CheckCircle2,FileDown,FileUp,LoaderCircle,UserPlus,X} from 'lucide-react';
import {channel,eur} from '../api';
import {STATIC_MODE} from '../staticApi';
import '../customer-import.css';
type Preview={customer_id:string;stored:boolean;warnings:string[];contact_channels:string[];
 customer:{city:string;household_size:number;preferred_contact_language:string;customer_since:string;birth_year:number|null;portal_account:boolean;app_installed:boolean};
 consents:Record<string,string>;decision:{action:string;name:string;reason:string;expected_gain_eur:number}};
type Problem={errors:string[];warnings:string[]};
const consentLabel:Record<string,string>={newsletter_email:'Newsletter',marketing_email:'Marketing email',marketing_phone:'Phone',marketing_sms:'SMS',portal_app_personalisation:'Portal & app',profiling_analytics:'Profiling'};
const statusLabel:Record<string,string>={granted:'Granted',not_given:'Not given',withdrawn:'Withdrawn'};
// The server answers 422 with every problem at once; request() in api.ts only keeps string details, so post directly.
async function send(filename:string,content:string,dry_run:boolean):Promise<Preview>{
 const r=await fetch('/api/customers/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename,content,dry_run})});
 const body=await r.json().catch(()=>({}));
 if(r.ok)return body as Preview;
 const d=body.detail;throw d&&Array.isArray(d.errors)?d as Problem:{errors:[typeof d==='string'?d:'The server could not check this file ('+r.status+').'],warnings:[]};
}
export default function CustomerImport({open,onClose,onCreated}:{open:boolean;onClose:()=>void;onCreated:(id:string)=>void}){
 const modal=useRef<HTMLDialogElement>(null),picker=useRef<HTMLInputElement>(null);
 const[file,setFile]=useState<{name:string;content:string}|null>(null),[preview,setPreview]=useState<Preview|null>(null),[problem,setProblem]=useState<Problem|null>(null),[busy,setBusy]=useState<''|'checking'|'creating'>(''),[drag,setDrag]=useState(false);
 useEffect(()=>{if(open)modal.current?.showModal();else{modal.current?.close();setFile(null);setPreview(null);setProblem(null);setBusy('')}},[open]);
 async function check(f:File){
  setPreview(null);setProblem(null);
  if(f.size>100_000){setProblem({errors:['The file is larger than 100 KB.'],warnings:[]});return}
  const content=await f.text();setFile({name:f.name,content});setBusy('checking');
  try{setPreview(await send(f.name,content,true))}catch(e){setProblem(e as Problem)}finally{setBusy('')}
 }
 async function create(){
  if(!file)return;setBusy('creating');setProblem(null);
  try{const result=await send(file.name,file.content,false);onCreated(result.customer_id)}catch(e){setProblem(e as Problem);setBusy('')}
 }
 const c=preview?.customer;
 return <dialog ref={modal} className="developer-dialog import-dialog" aria-labelledby="import-title" onCancel={e=>{e.preventDefault();if(!busy)onClose()}}>
  <div className="developer-dialog-header"><div><UserPlus size={21}/><div><h2 id="import-title">Import a customer</h2><p>One customer per file · master data and contact consents.</p></div></div><button className="button icon-button" aria-label="Close import" disabled={!!busy} onClick={onClose}><X size={19}/></button></div>
  <div className="developer-dialog-content">{STATIC_MODE?<div className="notice">This is a read-only demo. Start the full app with its FastAPI backend to import customers.</div>:<>
   <label className={'import-drop'+(drag?' dragging':'')+(busy?' busy':'')} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);const f=e.dataTransfer.files[0];if(f&&!busy)check(f)}}>
    <input ref={picker} type="file" accept=".csv,.json,text/csv,application/json" disabled={!!busy} onChange={e=>{const f=e.target.files?.[0];if(f)check(f);e.target.value=''}}/>
    {busy==='checking'?<LoaderCircle className="loading-spin" size={24}/>:<FileUp size={24}/>}
    <b>{busy==='checking'?'Checking the file and scoring the customer…':file?file.name:'Choose a CSV or JSON file'}</b>
    <small>{busy==='checking'?'The engine evaluates the customer before anything is stored.':file?'Choose another file to replace it.':'Or drop it here. Nothing is stored until you confirm.'}</small>
   </label>
   <p className="import-templates">Need the format? <a href="/api/customers/import/template?format=csv" download><FileDown size={13}/>CSV template</a><a href="/api/customers/import/template?format=json" download><FileDown size={13}/>JSON template</a></p>
   {problem&&<div className="import-problems" role="alert"><b><AlertTriangle size={16}/>{problem.errors.length===1?'This file cannot be imported':`${problem.errors.length} problems in this file`}</b><ul>{problem.errors.map((e,i)=><li key={i}>{e}</li>)}</ul><small>Fix the file and choose it again. Nothing was stored.</small></div>}
   {preview&&c&&<section className="import-preview" aria-label="Import preview">
    <div className="import-preview-head"><span className="workspace-caption">New customer</span><h3>{preview.customer_id}</h3><p>{c.city} · household of {c.household_size} · {c.preferred_contact_language.toUpperCase()} · since {c.customer_since}{c.birth_year?` · born ${c.birth_year}`:''}</p></div>
    <dl className="import-facts"><div><dt>Portal account</dt><dd>{c.portal_account?'Yes':'No'}</dd></div><div><dt>App installed</dt><dd>{c.app_installed?'Yes':'No'}</dd></div><div><dt>Contracts</dt><dd>None yet · CLV starts at {eur(0)}</dd></div></dl>
    <h4>Recorded consents</h4><ul className="import-consents">{Object.entries(preview.consents).map(([k,v])=><li key={k} className={v}><span>{consentLabel[k]||k}</span><b>{statusLabel[v]||v}</b></li>)}</ul>
    <div className="import-decision"><span>Engine next action</span><b>{preview.decision.name}</b><p>{preview.decision.reason}</p><small>Contact channels: {preview.contact_channels.length?preview.contact_channels.map(channel).join(', '):'none'} · estimated gain {eur(preview.decision.expected_gain_eur)}</small></div>
    {!!preview.warnings.length&&<ul className="import-warnings">{preview.warnings.map((w,i)=><li key={i}><AlertTriangle size={13}/>{w}</li>)}</ul>}
   </section>}
   <div className="developer-key-actions import-actions"><button className="button primary" disabled={!preview||!!busy} onClick={create}>{busy==='creating'?<LoaderCircle className="loading-spin" size={15}/>:<CheckCircle2 size={15}/>}{busy==='creating'?'Creating customer…':'Create customer'}</button><button className="button" disabled={!!busy} onClick={onClose}>Cancel</button></div>
   <p className="developer-key-note">Imported rows are added next to the source data and can't be changed or deleted afterwards. Every import is written to the audit log.</p>
  </>}</div>
 </dialog>
}
