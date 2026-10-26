import {useCustomerDecision} from './CustomerDecisionContext';
import {useChannelPolicy} from './ChannelPolicy';
import {useEffect, useState} from 'react';
import {Sparkles, RefreshCw, ArrowUpRight, Check, ChevronDown, ShieldCheck} from 'lucide-react';
import {request, useApi, channel, eur} from '../api';
import type {Customer,Catalog,Product} from '../types';
import {destination,productDescriptions} from './productPresentation';
import OutreachWorkbench from './OutreachWorkbench';
import {Panel} from './ui';

type Evidence={fact_id:string;quote:string};
type Proposal={action:string;product_id:string|null;channel:string|null;need:string;rationale:string;customer_benefit:string;why_now:string;evidence:Evidence[];alternatives:string[];missing_data:string[]};
type Result={id:number;status:string;model:string;proposal:Proposal|null;baseline:{name:string;product_id:string|null;action:string};validation_errors:string[];error:string|null;email_error:string|null;email:{subject:string;body:string}|null;draft_id?:number;control_group:boolean;context:{facts:{id:string;source:string;quote:string}[];catalogue:Product[]}};
export type Latest={result:Result|null;current:boolean};
type Status={configured:boolean;model:string;provider:string};
function ProductCard({product,tone}:{product:Product;tone:string}){
 const target=destination(product.product_id),Icon=target.Icon;
 return <aside className="offer-product"><div className={'offer-product-image '+(target.image?'has-photo':'')}><Icon className="product-symbol" size={92} strokeWidth={1.25}/>{target.image&&<img src={target.image} alt={'MAINGAU '+target.category+' – Themenbild'} referrerPolicy="no-referrer" loading="lazy" onError={e=>{e.currentTarget.style.display='none'}}/>}<span className="product-category">MAINGAU {target.category}</span></div><div className="offer-product-info"><span className="eyebrow">{tone==='du'?'Für dich ausgewählt':'Für Sie ausgewählt'}</span><h3>{product.product_name}</h3><p>{productDescriptions[product.product_id]||product.description}</p><a className="product-cta" href={target.url} target="_blank" rel="noopener noreferrer">{target.label}<ArrowUpRight size={17}/></a><small>Produktvorschlag aus dem Demo-Katalog. Genaue Tarife und Verfügbarkeit bei MAINGAU prüfen.</small></div></aside>
}
function FactHighlights({result}:{result:Result}){
 const refs=result.proposal?.evidence.filter(e=>e.fact_id.startsWith('F')).slice(0,3)||[];
 return <div className="offer-evidence-strip">{refs.map((e,i)=>{const fact=result.context.facts.find(f=>f.id===e.fact_id);let values:Record<string,unknown>={};try{values=JSON.parse(e.quote)}catch{/* Full fact text stays available in the analyst detail. */}
 let label='Source observation',value=fact?.source.replaceAll('_',' ')||e.fact_id;
 if(typeof values.data_limit_reached_3m==='number'){label='Data limit · last 3 months';value=values.data_limit_reached_3m+'× reached'}
 else if(values.price_guarantee_until){label='Price guarantee ends';value=String(values.price_guarantee_until).slice(0,10)}
 else if(values.category){label='Customer service';value=String(values.category)+' · '+String(values.status||'recorded')}
 else if(typeof values.dunning_level==='number'&&values.dunning_level>0){label='Payment status';value='Dunning level '+values.dunning_level}
 else if(values.plan){label='Current mobile plan';value=String(values.plan)}
 else if(values.status==='open'){label='Service case';value='Open case'}
 else if(values.device_type){label='Connected device';value=String(values.device_type).replaceAll('_',' ')}
 else if(values.tariff){label='Current tariff';value=String(values.tariff)}
 else if(values.household_size){label='Household';value=String(values.household_size)+' people'}
 return <div key={i}><span>{label}</span><strong>{value}</strong><small>{e.fact_id} · source record</small></div>})}</div>
}
export default function AIDecision({customer,revision,onReview,busyReview,onNewsletterActive}:{customer:Customer;revision:number;onReview:(status:string)=>void;busyReview:boolean;onNewsletterActive:(active:boolean)=>void}){
 const id=customer.id;
 const{refresh:refreshChannels}=useChannelPolicy();
 const {data:status}=useApi<Status>('/ai/status',revision),{data:catalog}=useApi<Catalog>('/catalog',revision);
 const [mode,setMode]=useState<'ai'|'rules'>('ai');
 const {data:saved,error,refresh:refreshDecision}=useCustomerDecision();
 const [busy,setBusy]=useState(false),[failure,setFailure]=useState('');
 async function generate(){setBusy(true);setFailure('');try{await request('/customers/'+id+'/ai-nba','POST',{refresh:!!saved?.result});refreshDecision();refreshChannels()}catch(e){setFailure((e as Error).message)}finally{setBusy(false)}}
 const result=saved?.result,p=result?.proposal,isAI=mode==='ai';
 const usable=!!result&&result.status==='validated'&&!!saved?.current;
 const productId=isAI?(usable?p?.product_id:null):customer.decision.product_id;
 const product=(isAI?result?.context.catalogue:catalog?.products)?.find(v=>v.product_id===productId);
 const action=isAI?p?.action:customer.decision.action;
 const copy=isAI?(usable?result?.email:null):customer.decision.message;
 const actionable=isAI?usable&&['offer','service'].includes(action||''):['offer','service'].includes(action||'');
 const emptyTitles:Record<string,string>={none:'Heute ist kein neues Angebot nötig.',wait:'Ein guter Moment, kurz abzuwarten.',human_review:'Wir schauen uns dein Anliegen persönlich an.',service:'Dein Anliegen kommt zuerst.'};
 return <section className="nba-studio" aria-label="Next best action comparison"><header className="studio-toolbar"><div><div className="eyebrow">NEXT BEST ACTION</div><h2>A better next step.</h2></div><div className="mode-switch" role="group" aria-label="Recommendation version"><button aria-pressed={!isAI} className={!isAI?'active':''} onClick={()=>setMode('rules')}>Engine <span>CLV ranked</span></button><button aria-pressed={isAI} className={isAI?'active ai-active':''} onClick={()=>setMode('ai')}><Sparkles size={14}/>AI <span>personalised</span></button></div></header>
 <div className="preview-toolbar"><span><i className={'preview-dot '+(isAI?'ai':'')}/>{isAI?'Personalised offer workspace':'Engine decision'}</span><span>{isAI?'Offer & channel preview':'Customer preview'} · {customer.tone==='du'?'Du':'Sie'}</span></div>
 {(failure||error)&&<p className="ai-warning studio-alert">{failure||error}</p>}
 {isAI&&(!result||!usable)?<div className="ai-empty"><div className="sparkle-orb"><Sparkles size={27}/></div><h3>{busy?'Finding the right next step…':!result?'Turn customer context into an offer.':!saved?.current?'This offer needs a fresh look.':'This suggestion needs correction.'}</h3><p>{busy?'The model analyses the full catalogue and source facts, then writes a separate German draft.':!result?'AI connects the customer’s needs with a suitable product. Generate an offer to preview it here.':!saved?.current?'Customer context or policy changed. Generate again before using the saved suggestion.':'The server blocked this result. The engine decision is available under Engine.'}</p>{result?.error&&<p className="muted">{result.error}</p>}{result?.validation_errors.length?<details><summary>Why this result was blocked</summary><ul>{result.validation_errors.map((v,i)=><li key={i}>{v}</li>)}</ul></details>:null}<button className="button primary" disabled={busy||!status?.configured} onClick={generate}><Sparkles size={15}/>{busy?'Analysing…':'Generate personalised offer'}</button></div>:<>
 {isAI&&usable&&result&&product&&actionable?<OutreachWorkbench key={id+result.id} customer={customer} decisionId={result.id} product={product} revision={revision} isService={action==='service'} onNewsletterActive={onNewsletterActive}/>:<div className={'offer-preview '+(!actionable?'no-product':'')}><article className="offer-message"><div className="offer-brand">MAINGAU<span>+</span></div><div className="offer-kicker">{action==='service'?(customer.tone==='du'?'Wir sind für dich da':'Wir sind für Sie da'):isAI?(customer.tone==='du'?'Ein Vorschlag, der zu dir passt':'Ein Vorschlag, der zu Ihnen passt'):'Unsere Empfehlung'}</div><h2>{copy?.subject||(emptyTitles[action||'none']||'Der nächste Schritt mit MAINGAU').replace('dein',customer.tone==='du'?'dein':'Ihr').replace('Dein',customer.tone==='du'?'Dein':'Ihr')}</h2>{copy?<div className="customer-copy">{copy.body.split(/\n\s*\n/).map((paragraph,i)=><p key={i}>{paragraph}</p>)}</div>:<p className="customer-copy">{isAI&&actionable?'The product choice is saved. Customer copy still needs to be generated.':'Aktuell steht kein neues Produktangebot an. Der nächste Schritt wird auf die persönliche Situation abgestimmt.'}</p>}

 <div className="offer-signature">{customer.tone==='du'?'Dein':'Ihr'} MAINGAU Team</div></article>{actionable&&product&&<ProductCard product={product} tone={customer.tone}/>}</div>}
 </>}
 <footer className="studio-footer"><div><ShieldCheck size={15}/><span>{isAI?(result?.control_group?'Control group · held out':usable?'NBA decision checked · material checked separately':'AI comparison · not ready for delivery'):'Rules baseline · expected CLV gain '+eur(customer.decision.expected_gain_eur)}<small>{isAI?'Preview only. Tariff eligibility and savings still require verification.':'Original template and deterministic product selection.'}</small></span></div><div className="inline">{isAI?<>{result&&<button className="button" disabled={busy||!status?.configured} onClick={generate}><RefreshCw size={14}/>{busy?'Analysing…':'Rethink NBA'}</button>}</>:!customer.decision.control_group&&actionable&&<><button className="button primary" disabled={busyReview||customer.decision.status==='approved'} onClick={()=>onReview('approved')}><Check size={14}/>{customer.decision.status==='approved'?'Approved':'Approve baseline'}</button><button className="button" disabled={busyReview} onClick={()=>onReview('rejected')}>Reject</button></>}</div></footer>
 <details className="analyst-details"><summary><ChevronDown size={15}/>Decision details & source evidence<span>{isAI?'AI analysis':'Rules analysis'}</span></summary><div className="analyst-body">{isAI&&p&&result?<><FactHighlights result={result}/><div className="two-columns"><div><h3>Customer need</h3><p>{p.need}</p><h3>Benefit</h3><p>{p.customer_benefit}</p></div><div><h3>Why this action now</h3><p>{p.rationale}</p><p>{p.why_now}</p><p className="muted">Channel: {channel(p.channel)} · {result.model}</p></div></div><div className="two-columns"><div><h3>Alternatives</h3><ul>{p.alternatives.map((v,i)=><li key={i}>{v}</li>)}</ul></div><div><h3>Missing information</h3><ul>{p.missing_data.map((v,i)=><li key={i}>{v}</li>)}</ul></div></div><details><summary>Source references · {p.evidence.length}</summary>{p.evidence.map((e,i)=><div className="source-reference" key={i}><b>{e.fact_id} · {result.context.facts.find(f=>f.id===e.fact_id)?.source||'product catalogue'}</b><pre className="fact-quote">{e.quote}</pre></div>)}</details><a href={'/api/customers/'+id+'/ai-context'} target="_blank" rel="noreferrer">Inspect model input <ArrowUpRight size={12}/></a>{result.email_error&&<p className="ai-warning">{result.email_error}</p>}</>:<><p>{customer.decision.reason}</p><p>{channel(customer.decision.channel)} · {customer.decision.p_accept!==null?(customer.decision.p_accept*100).toFixed(1)+'% estimated acceptance':'No acceptance estimate'}</p><ul>{customer.decision.log.map((v,i)=><li key={i}>{v}</li>)}</ul></>}</div></details>
 </section>
}
type Job={id:number;status:string;completed:number;total:number;results:{customer_id:string;status:string;action:string|null;product_id:string|null}[]};
export function AISample({onSelect}:{onSelect:(id:string)=>void}){
  const [job,setJob]=useState<Job|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{let live=true;async function poll(){try{const r=await request<{job:Job|null}>('/ai/batches/latest');if(live)setJob(r.job)}catch(e){if(live)setError((e as Error).message)}}poll();const timer=setInterval(poll,4000);return()=>{live=false;clearInterval(timer)}},[]);
  async function start(limit:number){setBusy(true);setError('');try{setJob(await request<Job>('/ai/batches','POST',{limit}))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  const running=job&&['queued','running'].includes(job.status);
  return <Panel title="AI comparison sample" subtitle="Full catalogue decisions, checked against policy and saved alongside the rules baseline" action={<div className="inline"><button className="button" disabled={busy||!!running} onClick={()=>start(3)}><Sparkles size={14}/>Run 3 customers</button><button className="button" disabled={busy||!!running} onClick={()=>start(30)}><RefreshCw size={14}/>Evaluate 30 customers</button></div>}>
    <p className="muted small-text">Uses the configured team model. Each actionable result can use a second request for the email. No messages are sent.</p>
    {error&&<p className="ai-warning">{error}</p>}{job&&<><p><b>{job.status}</b> · {job.completed} / {job.total} customers</p><progress className="ai-progress" max={job.total} value={job.completed}/><div className="ai-results">{job.results.map(r=><button className="button" key={r.customer_id} onClick={()=>onSelect(r.customer_id)}>{r.customer_id} · {r.product_id||r.action||r.status} · {r.status}</button>)}</div></>}
  </Panel>
}
