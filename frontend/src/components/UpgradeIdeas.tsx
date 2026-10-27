import {useState} from 'react';
import {Lightbulb,LoaderCircle,ExternalLink,MessageCircle} from 'lucide-react';
import {STATIC_MODE} from '../staticApi';
import {request} from '../api';
import {categoryLink} from './productPresentation';

export type UpgradeItem={id:string;category:string;name:string;provider?:string;status?:string;external?:boolean;details?:Record<string,unknown>};
export type Idea={title:string;problem:string;benefit:string};

// Three AI-proposed upgrades for one known product, grounded in the MAINGAU catalogue.
// Discussing an idea with the advisor in a chat is a planned follow-up; for now the ideas
// link to the verified MAINGAU product page instead.
export default function UpgradeIdeas({cid,product}:{cid:string;product:UpgradeItem}){
 const[open,setOpen]=useState(false),[busy,setBusy]=useState(false),[ideas,setIdeas]=useState<Idea[]>([]),[source,setSource]=useState(''),[note,setNote]=useState(''),[error,setError]=useState('');
 const link=categoryLink(product.category);
 async function load(){
  setBusy(true);setError('');setNote('');
  try{
   const r=await request<{ideas:Idea[];source:string;note:string|null}>('/customers/'+cid+'/upgrade-ideas','POST',{
    product_id:product.id,name:product.name,category:product.category,
    provider:product.provider||'',status:product.status||'',details:product.details||{}});
   setIdeas(r.ideas);setSource(r.source);setNote(r.note||'');setOpen(true);
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <div className="upgrade-ideas">
  <button className="button small" disabled={busy||STATIC_MODE} title={STATIC_MODE?'Run the full app to generate AI ideas':'Propose three ways to upgrade this product'} onClick={()=>open?setOpen(false):load()}>
   {busy?<LoaderCircle size={13} className="spin"/>:<Lightbulb size={13}/>}Upgrade ideas
  </button>
  {error&&<p className="ai-warning">{error}</p>}
  {open&&<div className="upgrade-list">
   {ideas.map((idea,i)=><article key={i} className="upgrade-card">
    <h4>{idea.title}</h4><p><b>Why now:</b> {idea.problem}</p><p><b>Benefit:</b> {idea.benefit}</p>
   </article>)}
   <p className="small-text muted upgrade-foot">
    {source==='ai'?'AI suggestions grounded in the MAINGAU catalogue.':'Catalogue-based standard suggestions.'}{' '}
    Verify conditions on <a href={link.url} target="_blank" rel="noreferrer">{link.label}<ExternalLink size={11}/></a>.{' '}
    <span className="upgrade-chat-hint"><MessageCircle size={11}/>Discussing an idea in chat with the advisor is coming soon.</span>
   </p>
   {note&&<p className="small-text muted">{note}</p>}
  </div>}
 </div>;
}
