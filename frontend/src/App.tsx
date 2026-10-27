import {useEffect,useState} from 'react';
import {Code2} from 'lucide-react';
import Sidebar from './components/Sidebar';
import Breadcrumbs from './components/Breadcrumbs';
import ThemePicker from './components/ThemePicker';
import Overview from './pages/Overview';
import Recommendations from './pages/Recommendations';
import Marketing from './pages/Marketing';
import Customers from './pages/Customers';
import DeveloperArea from './components/DeveloperArea';
import ServiceFirst from './pages/ServiceFirst';
import AssistantChat from './components/AssistantChat';
import {useApi} from './api';
const views=['overview','recommendations','service','marketing','customers','method'] as const;
type View=typeof views[number];
const titles:Record<View,string>={overview:'Overview',recommendations:'Recommendations',service:'Service first',marketing:'Marketing',customers:'Customer 360°',method:'How it works'};
function initial():View{const v=location.hash.slice(1).split('?')[0];return views.includes(v as View)?v as View:'overview'}
export default function App(){
 const[view,setView]=useState<View>(initial),[selected,setSelected]=useState(()=>new URLSearchParams(location.hash.split('?')[1]||'').get('customer')||null),[revision,setRevision]=useState(0),[toast,setToast]=useState(''),[developerOpen,setDeveloperOpen]=useState(false),[developerTab,setDeveloperTab]=useState<'connection'|'architecture'>('connection');
 const{data:health}=useApi<{status:string;customers:number}>('/health');
 function go(v:View){if(v==='method'){setDeveloperTab('architecture');setDeveloperOpen(true);return}if(v==='customers'){const p=new URLSearchParams(view==='customers'?location.hash.split('?')[1]||'':'');p.delete('customer');p.delete('tab');location.hash='customers'+(p.size?'?'+p.toString():'');setSelected(null)}else location.hash=v;setView(v)}
 useEffect(()=>{const fn=()=>{setView(initial());const cid=new URLSearchParams(location.hash.split('?')[1]||'').get('customer');setSelected(cid&&/^MG-\d+$/.test(cid)?cid:null)};window.addEventListener('hashchange',fn);return()=>window.removeEventListener('hashchange',fn)},[]);
 const select=(id:string)=>{setSelected(id);const p=new URLSearchParams(view==='customers'?location.hash.split('?')[1]||'':'');p.set('customer',id);p.delete('tab');location.hash='customers?'+p.toString();setView('customers')};
 const changed=()=>setRevision(v=>v+1);
 return <div className="app"><a className="skip-link" href="#main-content" onClick={e=>{e.preventDefault();document.getElementById('main-content')?.focus();document.getElementById('main-content')?.scrollIntoView()}}>Skip to main content</a><Sidebar view={view==='method'?'overview':view} onNavigate={go} onDeveloper={()=>{setDeveloperTab('connection');setDeveloperOpen(true)}}/><div className="main-shell">
  <header className="topbar"><Breadcrumbs view={view} title={titles[view]} customerId={selected}/><div className="topbar-right"><button className="button mobile-developer-entry" aria-label="Open Developer area" onClick={()=>{setDeveloperTab('connection');setDeveloperOpen(true)}}><Code2 size={15}/></button><ThemePicker/></div></header>
  {toast&&<div className="toast" role="status"><span>{toast}</span><button onClick={()=>setToast('')}>Dismiss</button></div>}
  <main id="main-content" tabIndex={-1}>{(view==='overview'||view==='method')&&<Overview revision={revision} onGo={go} onSelect={select}/>} {view==='recommendations'&&<Recommendations revision={revision} onSelect={select}/>} {view==='service'&&<ServiceFirst revision={revision} onSelect={select}/>} {view==='marketing'&&<Marketing revision={revision} onSelect={select} onChanged={changed} notify={setToast}/>} {view==='customers'&&<Customers id={selected} onSelect={select} revision={revision} onChanged={changed} notify={setToast}/>}</main>
  <footer><span>MAINGAU NBA Console</span><span>{health?.customers??750} synthetic customers · Snapshot 30 Sep 2026 · Estimates, not guaranteed results</span></footer>
 </div><AssistantChat onSelect={select} onConnect={()=>{setDeveloperTab('connection');setDeveloperOpen(true)}}/><DeveloperArea open={developerOpen||view==='method'} initialTab={view==='method'?'architecture':developerTab} onClose={()=>{setDeveloperOpen(false);if(view==='method'){location.hash='overview';setView('overview')}}} onConfigured={changed} revision={revision}/></div>
}
