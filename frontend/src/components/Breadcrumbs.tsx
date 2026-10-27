import {ChevronRight} from 'lucide-react';

export function customerListHref(hash:string){
 const params=new URLSearchParams(hash.split('?')[1]||'');
 params.delete('customer');params.delete('tab');
 return '#customers'+(params.size?'?'+params.toString():'');
}

export default function Breadcrumbs({view,title,customerId}:{view:string;title:string;customerId:string|null}){
 const detail=view==='customers'&&customerId;
 const crumbs=view==='overview'?[{label:'Overview'}]:[
  {label:'Overview',href:'#overview'},
  ...(detail?[{label:'Customers',href:customerListHref(location.hash)},{label:customerId}]:[{label:view==='customers'?'Customers':title}]),
 ];
 return <nav className="workspace-breadcrumbs" aria-label="Breadcrumb"><ol>{crumbs.map((crumb,i)=><li key={crumb.label}>{i>0&&<ChevronRight size={13} aria-hidden="true"/>}{'href' in crumb?<a href={crumb.href}>{crumb.label}</a>:<span aria-current="page">{crumb.label}</span>}</li>)}</ol></nav>;
}
