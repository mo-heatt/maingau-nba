import {useLayoutEffect,useRef,useState} from 'react';
import type {CSSProperties,PointerEvent} from 'react';
import {ChevronLeft,ChevronRight,LayoutDashboard,SlidersHorizontal,UsersRound,Workflow,Database,ShieldCheck} from 'lucide-react';
const items=[['recommendations','Recommendations',LayoutDashboard],['marketing','Marketing',SlidersHorizontal],['customers','Customer 360°',UsersRound],['method','How it works',Workflow]] as const;
type View=typeof items[number][0];
function initialCollapsed(){try{const saved=localStorage.getItem('maingau-navigation-collapsed');if(saved!==null)return saved==='true'}catch{/* Keep navigation usable without storage. */}return window.matchMedia('(max-width: 950px)').matches}
export default function Sidebar({view,onNavigate}:{view:View;onNavigate:(view:View)=>void}){
 const[collapsed,setCollapsed]=useState(initialCollapsed),[edge,setEdge]=useState(false),[tracking,setTracking]=useState(false);
 const panel=useRef<HTMLElement>(null);
 useLayoutEffect(()=>{
  const element=panel.current;if(!element)return;
  const align=()=>{
   const active=element.querySelector<HTMLElement>('[aria-current="page"]');if(!active)return;
   const box=element.querySelector('nav')!.getBoundingClientRect(),item=active.getBoundingClientRect();
   element.style.setProperty('--active-y',item.top-box.top+item.height/2+'px');
  };
  align();const observer=new ResizeObserver(align);observer.observe(element);observer.observe(element.querySelector('nav')!);
  return()=>observer.disconnect();
 },[view,collapsed]);
 function follow(event:PointerEvent<HTMLElement>){
  if(event.pointerType==='touch')return;
  setTracking(true);
  const box=event.currentTarget.getBoundingClientRect();
  const navBox=event.currentTarget.querySelector('nav')!.getBoundingClientRect();
  panel.current?.style.setProperty('--cursor-y',Math.min(navBox.height-5,Math.max(5,event.clientY-navBox.top))+'px');
  const nearEdge=event.clientX>=box.right-28;
  setEdge(nearEdge);
  if(nearEdge)panel.current?.style.setProperty('--toggle-y',Math.min(box.height-44,Math.max(48,event.clientY-box.top))+'px');
 }
 function toggle(){setCollapsed(old=>{const next=!old;try{localStorage.setItem('maingau-navigation-collapsed',String(next))}catch{/* Session-only choice. */}return next})}
 return <aside ref={panel} className={'sidebar '+(collapsed?'is-collapsed':'is-expanded')} data-edge={edge} data-tracking={tracking} onPointerMove={follow} onPointerLeave={()=>{setEdge(false);setTracking(false)}} style={{'--toggle-y':'160px'} as CSSProperties}>
  <a className="brand" href="#recommendations" aria-label="MAINGAU · Recommendations"><b className="brand-word">MAINGAU</b><span className="brand-mark">+</span></a>
  <div className="brand-sub">NEXT BEST ACTION</div><div className="nav-label">WORKSPACE</div>
  <nav id="workspace-navigation" aria-label="Main navigation">{items.map(([key,label,Icon])=><button key={key} className={'nav-item'+(view===key?' active':'')} aria-label={label} aria-current={view===key?'page':undefined} title={collapsed?label:undefined} onClick={()=>onNavigate(key)}><Icon size={19}/><span className="nav-copy">{label}</span>{view===key&&<span className="nav-indicator" aria-hidden="true"/>}</button>)}<div className="navigation-track" aria-hidden="true"/><span className="navigation-current-dot" aria-hidden="true"/><span className="navigation-cursor-dot" aria-hidden="true"/></nav>
  <div className="sidebar-bottom"><div><Database size={16}/><span>SQLite · persistent state</span></div><div><ShieldCheck size={16}/><span>One server-side engine</span></div><p>Synthetic data · Build Days MVP<br/>No external sending</p></div>
  <button className="sidebar-toggle" aria-label={collapsed?'Expand navigation':'Collapse navigation'} aria-expanded={!collapsed} aria-controls="workspace-navigation" onClick={toggle}>{collapsed?<ChevronRight size={18}/>:<ChevronLeft size={18}/>}</button>
 </aside>
}
