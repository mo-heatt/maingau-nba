import {createContext,useContext,useState} from 'react';
import type {ReactNode} from 'react';
import type {Customer} from '../types';
import {CheckCircle2,XCircle} from 'lucide-react';
import {useApi} from '../api';
import type {Quote,Dossier} from './OutreachWorkbench';
export type ChannelPolicy={decision_id:number|null;quote:Quote|null;dossier:Dossier;current:boolean;editorial_newsletter_allowed:boolean;editorial_newsletter:{allowed:boolean;reasons:string[]};allowed_channels:string[];channels:{channel:string;label:string;allowed:boolean;reasons:string[];contact_allowed:boolean|null;contact_reason:string|null}[]};
const Context=createContext<{data:ChannelPolicy|null;error:string;loading:boolean;refresh:()=>void}>({data:null,error:'',loading:true,refresh:()=>{}});
export function ChannelPolicyProvider({id,revision,children}:{id:string;revision:number;children:ReactNode}){
 const[tick,setTick]=useState(0);
 const state=useApi<ChannelPolicy>('/customers/'+id+'/outreach-context',revision+tick);
 return <Context.Provider value={{...state,data:state.loading?null:state.data,refresh:()=>setTick(v=>v+1)}}>{children}</Context.Provider>;
}
export const useChannelPolicy=()=>useContext(Context);
export function ChannelPermissions(){
 const{data,error}=useChannelPolicy();
 if(!data)return <p className="small-text muted">{error||'Checking channel eligibility…'}</p>;
 return <><p className="small-text muted">Decision availability is derived from source consent and policy checks. A blocked action does not change the recorded consent.</p><div className="checks">{data.channels.map(ch=><p key={ch.channel} className={ch.allowed?'':'muted'}>{ch.allowed?<CheckCircle2 size={14}/>:<XCircle size={14}/>}<span>{ch.label}<small>{ch.allowed?'Available for this recommendation':ch.reasons.join(' · ')}</small><small>{ch.contact_allowed===null?ch.contact_reason:ch.contact_allowed?'Contact permission granted':'Contact permission: '+ch.contact_reason}</small></span></p>)}</div><p className="small-text"><b>Informational newsletter: {data.editorial_newsletter.allowed?'available':'unavailable'}</b><br/>{data.editorial_newsletter.allowed?'Separate purpose: helpful updates without a personalised product offer.':data.editorial_newsletter.reasons.join(' · ')}</p></>;
}

const consentLabels:Record<string,string>={newsletter_email:'Newsletter email',marketing_email:'Marketing email',marketing_phone:'Marketing phone',marketing_sms:'Marketing SMS',portal_app_personalisation:'Portal & app personalisation',profiling_analytics:'Profiling & analytics'};
export function RecordedConsents({customer}:{customer:Customer}){
 return <><p className="small-text muted">Imported from consent_status in SQLite. These are source records, independent of the AI recommendation.</p><div className="recorded-consents">{Object.entries(customer.consent).map(([kind,value])=><div key={kind} className="recorded-consent"><div><b>{consentLabels[kind]||kind}</b><span className={'consent-status '+(value.status==='granted'?'granted':'restricted')}>{value.status==='granted'?'Granted':value.status==='withdrawn'?'Withdrawn':'Not given'}</span></div><small>Updated {value.updated_at} · {value.source.replaceAll('_',' ')}</small>{kind==='newsletter_email'&&<small>Double opt-in: {value.doi||'Not recorded'}</small>}</div>)}</div>{customer.decision.control_group&&<div className="consent-holdout"><b>Consent is preserved. Contact is held back for measurement.</b><p>This customer belongs to the stable 10% control group. The demo blocks campaign generation even when a channel has consent. AI did not withdraw any permission.</p></div>}</>;
}
