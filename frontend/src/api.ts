import {useEffect,useState} from 'react';
import {STATIC_MODE,staticRequest} from './staticApi';
export async function request<T>(path:string,method='GET',body?:unknown,signal?:AbortSignal):Promise<T>{if(STATIC_MODE){const result=await staticRequest<T>(path,method,body);if(method!=='GET'){readEpoch++;reads.clear();pending.clear()}return result;}const r=await fetch('/api'+path,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,signal});if(!r.ok){const d=await r.json().catch(()=>({}));throw Error(typeof d.detail==='string'?d.detail:'Request failed ('+r.status+')')}if(method!=='GET'){readEpoch++;reads.clear();pending.clear()}return r.json() as Promise<T>}
// Cache only reads, for one browser session. Mutations invalidate every view;
// the server still rechecks current permissions before generating any material.
const reads=new Map<string,{value:unknown;expires:number}>();
const pending=new Map<string,Promise<unknown>>();
let readEpoch=0;
function read<T>(path:string,revision:number):Promise<T>{
 const key=path+'@'+revision,hit=reads.get(key);
 if(hit&&hit.expires>Date.now())return Promise.resolve(hit.value as T);
 const existing=pending.get(key);if(existing)return existing as Promise<T>;
 const epoch=readEpoch;
 const work=request<T>(path).then(value=>{if(epoch===readEpoch){if(reads.size>=100)reads.delete(reads.keys().next().value!);reads.set(key,{value,expires:Date.now()+30000})}return value}).finally(()=>{if(pending.get(key)===work)pending.delete(key)});
 pending.set(key,work);return work;
}
export function useApi<T>(path:string,revision=0){
 const key=path+'@'+revision;
 const cached=()=>{const hit=reads.get(key);return hit&&hit.expires>Date.now()?hit.value as T:null};
 const[state,setState]=useState<{key:string;data:T|null;error:string;loading:boolean}>(()=>{const data=cached();return{key,data,error:'',loading:data===null}});
 useEffect(()=>{let active=true;const data=cached();setState({key,data,error:'',loading:data===null});read<T>(path,revision).then(data=>{if(active)setState({key,data,error:'',loading:false})}).catch(e=>{if(active)setState({key,data:null,error:e.message,loading:false})});return()=>{active=false}},[path,revision]);
 return state.key===key?{data:state.data,error:state.error,loading:state.loading}:{data:cached(),error:'',loading:cached()===null};
}
export const eur=(v:number)=>new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR',maximumFractionDigits:2}).format(v);
export const channel=(c:string|null)=>({'portal_popup':'Portal pop-up','app_push':'App push','newsletter_email':'Newsletter','email':'Marketing email','sms':'SMS','outbound_call':'Phone','agent_callback':'Service callback'}[c||'']||c||'—');
