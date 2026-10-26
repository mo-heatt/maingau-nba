import {createContext,useContext,useState} from 'react';
import type {ReactNode} from 'react';
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
 return <><p className="small-text muted">Availability for the current AI recommendation. Consent alone does not make a channel eligible.</p><div className="checks">{data.channels.map(ch=><p key={ch.channel} className={ch.allowed?'':'muted'}>{ch.allowed?<CheckCircle2 size={14}/>:<XCircle size={14}/>}<span>{ch.label}<small>{ch.allowed?'Available for this recommendation':ch.reasons.join(' · ')}</small><small>{ch.contact_allowed===null?ch.contact_reason:ch.contact_allowed?'Contact permission granted':'Contact permission: '+ch.contact_reason}</small></span></p>)}</div><p className="small-text"><b>Informational newsletter: {data.editorial_newsletter.allowed?'available':'unavailable'}</b><br/>{data.editorial_newsletter.allowed?'Separate purpose: helpful updates without a personalised product offer.':data.editorial_newsletter.reasons.join(' · ')}</p></>;
}
