import {ArrowRight,Check,Headphones,ShieldCheck,Sparkles,Clock3,FileText} from 'lucide-react';
import type {Customer} from '../types';
import {channel,eur} from '../api';
import {useCustomerDecision} from './CustomerDecisionContext';
import {useChannelPolicy} from './ChannelPolicy';
import {RadarBox} from '../pages/ServiceFirst';
import type {RadarCard} from '../pages/ServiceFirst';
const names:Record<string,string>={offer:'A relevant product offer',service:'Resolve the service issue',wait:'Wait before another contact',none:'No new contact needed',human_review:'A person should review this case'};
const labels:Record<string,string>={data_limit_reached:'Data allowance reached',open_complaint:'Open complaint',guarantee_ending:'Price guarantee ending',failed_charges:'Failed charging sessions',clicked_mobile:'Interest in mobile',clicked_shop:'Interest in the shop',smart_meter:'Smart meter recorded'};
export default function CustomerOverview({customer:c,stuck,onOpen}:{customer:Customer;stuck?:RadarCard;onOpen:(tab:string)=>void}){
 const{data:latest,loading}=useCustomerDecision(),{data:policy}=useChannelPolicy();
 const result=latest?.current&&latest.result?.status==='validated'?latest.result:null,p=result?.proposal;
 const action=p?.action||c.decision.action;
 const product=p?.product_id?result?.context.catalogue.find(v=>v.product_id===p.product_id):null;
 const title=p?(action==='offer'?policy?.quote?.target?.name||product?.product_name||names[action]:names[action]):c.decision.name;
 const source=p?'AI recommendation':'Engine recommendation';
 const holdout=result?.control_group??c.decision.control_group;
 const productId=p?.product_id||c.decision.product_id||'';
 const relevant=action==='service'?/complaint|dunning|failed|ticket|csat|cancel/:productId.startsWith('P-MO')?/data_limit|mobile|roaming/:productId.startsWith('P-EN')?/guarantee|meter|energy|tariff/:/clicked|guarantee|data_limit|complaint/;
 const signals=[...c.signals].filter(s=>relevant.test(s.key)).sort((a,b)=>Number(/complaint|data_limit|failed_charge|guarantee/.test(b.key))-Number(/complaint|data_limit|failed_charge|guarantee/.test(a.key)));
 const observations=signals.map(s=>({key:s.key,title:labels[s.key]||s.key.replaceAll('_',' '),detail:s.evidence.join(' · ')||String(s.value),source:s.class==='behavioural'?'Observed behaviour':s.class==='contract'?'Contract record':s.class}));
 if(policy?.quote?.current){const current=policy.quote.current;observations.splice(1,0,{key:'current-plan',title:'Current product',detail:[current.name,current.data_gb!==undefined?current.data_gb+' GB':null,current.monthly_eur!==undefined?eur(current.monthly_eur)+' / month':null].filter(Boolean).join(' · '),source:'Contract record'})}
 const visibleObservations=observations.slice(0,3);
 const need=(p?.need||c.decision.reason.split('. Via ')[0]).replace(/\s*\(F\d+(?:,\s*F\d+)*\)/g,'');
 return <>{stuck&&<RadarBox c={stuck}/>}<div className="customer-overview-grid"><section className={'customer-next-step action-'+action}><div className="next-step-top"><span>{p?<Sparkles size={15}/>:<FileText size={15}/>} {source}</span><span className="next-action-label">{holdout?'Control group · no contact':action==='service'?'Service first':action==='offer'?'Relevant opportunity':action==='wait'?'Respect the contact limit':'Contact decision'}</span></div><h2>{title}</h2>{holdout&&<p className="customer-holdout-note"><ShieldCheck size={15}/>Held out from contact to measure incremental uplift.</p>}<p className="next-step-reason">{need}</p>{p?.customer_benefit&&<div className="customer-benefit"><Check size={16}/><p>{p.customer_benefit}</p></div>}
 <div className="next-step-facts"><div><span>Suggested channel</span><b>{channel(p?.channel||c.decision.channel)}</b></div><div><span>Customer tone</span><b>{c.tone==='du'?'Du · informal':'Sie · formal'}</b></div><div><span>{p?'Decision status':'Estimated company gain'}</span><b>{holdout?'Held out · no delivery':p?'Source & policy checked':eur(c.decision.expected_gain_eur)}</b></div></div>
 <div className="next-step-footer"><button className="button primary" onClick={()=>onOpen('studio')}>{action==='service'?<Headphones size={15}/>:<Sparkles size={15}/>}{holdout||!['offer','service'].includes(action)?'Inspect decision':action==='service'?'Open service studio':'Open offer studio'}<ArrowRight size={15}/></button><small>{loading?'Checking saved AI recommendation…':result?'Saved AI proposal. Material is checked separately.':'Engine baseline. AI analysis is available in the studio.'}</small></div></section>
 <section className="customer-evidence"><div className="detail-section-heading"><h2>Why this customer?</h2><span>Source observations</span></div>{visibleObservations.length?visibleObservations.map(s=><div className="customer-observation" key={s.key}><span className="observation-mark"/><div><b>{s.title}</b><p>{s.detail}</p><small>{s.source}</small></div></div>):<div className="directory-empty"><FileText size={22}/><p>No additional signals are available.</p></div>}<button className="link" onClick={()=>onOpen('insights')}>Explore usage & activity<ArrowRight size={13}/></button></section></div>
 <div className="customer-contact-strip"><div><ShieldCheck size={20}/><span><b>{c.profiling?'Profiling consent granted':'Personalised profiling not permitted'}</b><small>{(()=>{const ok=c.channels.filter(x=>x.allowed).map(x=>channel(x.channel));return ok.length?`Contact allowed by ${ok.join(', ')}`:'No marketing channel has consent'})()}</small></span></div><div><Clock3 size={18}/><span><b>{c.contacts_30d} marketing contacts</b><small>In the source 30-day window</small></span></div><button className="button" onClick={()=>onOpen('permissions')}>Review permissions<ArrowRight size={13}/></button></div>
 {!stuck&&c.open_tickets.length>0&&<section className="customer-service-summary"><Headphones size={21}/><div><h3>{c.open_tickets.length} open service {c.open_tickets.length===1?'case':'cases'}</h3><p>{c.open_tickets[0].text||c.open_tickets[0].category}</p></div><button className="button" onClick={()=>onOpen('history')}>View service history</button></section>}
 </>
}
