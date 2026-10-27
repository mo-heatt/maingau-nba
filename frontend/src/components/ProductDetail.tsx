import {useEffect} from 'react';
import {X,ExternalLink} from 'lucide-react';
import {eur} from '../api';
import {categoryLink} from './productPresentation';
import UpgradeIdeas,{type UpgradeItem} from './UpgradeIdeas';

const RELATIONSHIP:Record<string,string>={contract:'Contract',purchase_record:'Purchase record',connected_device:'Connected device',competing_offer:'Competing offer · not a contract',reported_contract:'Customer reported'};

function formatDetail(key:string,value:unknown):string{
 if(typeof value==='number'){
  if(key==='monthly_eur')return eur(value)+' / month';
  if(key==='unit_eur_kwh')return value.toLocaleString('de-DE',{maximumFractionDigits:4})+' € / kWh';
  if(key==='base_eur_month')return eur(value)+' / month base';
  if(key==='ac_eur_kwh'||key==='dc_eur_kwh')return value.toLocaleString('de-DE',{maximumFractionDigits:4})+' € / kWh';
  if(key==='data_gb')return String(value)+' GB';
  if(key==='annual_kwh')return value.toLocaleString('de-DE')+' kWh / year';
  if(key==='quantity')return String(value)+'×';
 }
 if(typeof value==='string'&&/(until|_at|_end|date)$/.test(key)){
  const d=new Date(value.replace(' ','T'));
  if(!Number.isNaN(d.getTime()))return d.toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
 }
 return String(value);
}
const LABEL=(key:string)=>key.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());

// Detailed product page: every recorded fact, its source, the MAINGAU page for the category
// and the AI upgrade ideas in one place.
export default function ProductDetail({cid,product,onClose}:{cid:string;product:UpgradeItem & {source?:string;source_ref?:string;relationship?:string};onClose:()=>void}){
 useEffect(()=>{
  const onKey=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose()};
  window.addEventListener('keydown',onKey);
  return ()=>window.removeEventListener('keydown',onKey);
 },[onClose]);
 const link=categoryLink(product.category);
 const details=Object.entries(product.details||{});
 return <div className="product-detail-backdrop" onClick={onClose}>
  <section className="product-detail" role="dialog" aria-modal="true" aria-label={product.name+' details'} onClick={e=>e.stopPropagation()}>
   <header className="product-detail-head">
    <div>
     <span className="micro-tag">{product.provider||'Provider unknown'}</span>
     <h2>{product.name}</h2>
     <p className="small-text muted">{RELATIONSHIP[product.relationship||'']||'Product'} · {product.status?.replaceAll('_',' ')}</p>
    </div>
    <button className="button small" onClick={onClose} aria-label="Close product details"><X size={14}/>Close</button>
   </header>
   {details.length>0&&<div className="detail-grid">
    {details.map(([k,v])=>v!==null&&v!==undefined&&<div key={k}><span>{LABEL(k)}</span><b>{formatDetail(k,v)}</b></div>)}
   </div>}
   {(product.source||product.source_ref)&&<p className="small-text muted">Source: {product.source} · {product.source_ref}. Purchase records do not prove continuing ownership.</p>}
   {!product.external&&<a className="button maingau-link" href={link.url} target="_blank" rel="noreferrer">{link.label}<ExternalLink size={13}/></a>}
   <UpgradeIdeas cid={cid} product={product}/>
  </section>
 </div>;
}
