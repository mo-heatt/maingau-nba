import {useEffect,useState} from 'react';
import {ArrowUpRight} from 'lucide-react';
import Sidebar from './components/Sidebar';
import ThemePicker from './components/ThemePicker';
import Overview from './pages/Overview';
import Recommendations from './pages/Recommendations';
import Marketing from './pages/Marketing';
import Customer360 from './pages/Customer360';
import Method from './pages/Method';
import ServiceFirst from './pages/ServiceFirst';
import {useApi} from './api';
import {STATIC_MODE} from './staticApi';
const views=['overview','recommendations','service','marketing','customers','method'] as const;
type View=typeof views[number];
const titles:Record<View,string>={overview:'Overview',recommendations:'Recommendations',service:'Service first',marketing:'Marketing',customers:'Customer 360°',method:'How it works'};
function initial():View{const v=location.hash.slice(1).split('?')[0];return views.includes(v as View)?v as View:'overview'}
export default function App(){
 const[view,setView]=useState<View>(initial),[selected,setSelected]=useState(()=>new URLSearchParams(location.hash.split('?')[1]||'').get('customer')||'MG-100005'),[revision,setRevision]=useState(0),[toast,setToast]=useState('');
 const{data:health}=useApi<{status:string;customers:number}>('/health');
 function go(v:View){location.hash=v==='customers'?'customers?customer='+encodeURIComponent(selected):v;setView(v)}
 useEffect(()=>{const fn=()=>{setView(initial());const cid=new URLSearchParams(location.hash.split('?')[1]||'').get('customer');if(cid&&/^MG-\d+$/.test(cid))setSelected(cid)};window.addEventListener('hashchange',fn);return()=>window.removeEventListener('hashchange',fn)},[]);
 const select=(id:string)=>{setSelected(id);location.hash='customers?customer='+encodeURIComponent(id);setView('customers')};
 const changed=()=>setRevision(v=>v+1);
 return <div className="app"><Sidebar view={view} onNavigate={go}/><div className="main-shell">
  <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <b>{titles[view]}</b></div><div className="topbar-right"><ThemePicker/><span className="connection"><span className={health?'live-dot':'live-dot off'}/>{health?(STATIC_MODE?'Demo data loaded':'Backend connected'):'Connecting…'}</span>{!STATIC_MODE&&<a href="/api/docs" target="_blank">API docs<ArrowUpRight size={13}/></a>}<div className="avatar">MG</div></div></header>
  {toast&&<div className="toast" role="status"><span>{toast}</span><button onClick={()=>setToast('')}>Dismiss</button></div>}
  <main>{view==='overview'&&<Overview revision={revision} onGo={go} onSelect={select}/>} {view==='recommendations'&&<Recommendations revision={revision} onSelect={select}/>} {view==='service'&&<ServiceFirst revision={revision} onSelect={select}/>} {view==='marketing'&&<Marketing revision={revision} onSelect={select} onChanged={changed} notify={setToast}/>} {view==='customers'&&<Customer360 id={selected} onSelect={select} revision={revision} onChanged={changed} notify={setToast}/>} {view==='method'&&<Method revision={revision}/>}</main>
  <footer><span>MAINGAU NBA Console</span><span>{health?.customers??750} synthetic customers · Snapshot 30 Sep 2026 · Estimates, not guaranteed results</span></footer>
 </div></div>
}
