import {useEffect,useRef,useState} from 'react';
import {Code2,Compass,Radar,PanelLeftClose,PanelLeftOpen,LayoutDashboard,SlidersHorizontal,UsersRound} from 'lucide-react';
const items=[['overview','Overview',Compass],['recommendations','Recommendations',LayoutDashboard],['customers','Customer 360°',UsersRound],['service','Service first',Radar],['marketing','Marketing',SlidersHorizontal]] as const;
type View=typeof items[number][0];
function initialCollapsed(){try{const saved=localStorage.getItem('maingau-navigation-collapsed');if(saved!==null)return saved==='true'}catch{/* Keep navigation usable without storage. */}return window.matchMedia('(max-width: 950px)').matches}
export default function Sidebar({view,onNavigate,onDeveloper}:{view:View;onNavigate:(view:View)=>void;onDeveloper:()=>void}){
 const[collapsed,setCollapsed]=useState(initialCollapsed);
 const brandClick=useRef<ReturnType<typeof setTimeout>|null>(null);
 useEffect(()=>()=>{if(brandClick.current)clearTimeout(brandClick.current)},[]);
 function toggle(){setCollapsed(old=>{const next=!old;try{localStorage.setItem('maingau-navigation-collapsed',String(next))}catch{/* Session-only choice. */}return next})}
 return <aside className={'sidebar '+(collapsed?'is-collapsed':'is-expanded')}>
  <a className="brand" href="#overview" aria-label="MAINGAU · Overview" title="Double-click for Developer area" onClick={e=>{if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;e.preventDefault();if(e.detail===0){onNavigate('overview');return}if(brandClick.current)clearTimeout(brandClick.current);brandClick.current=setTimeout(()=>onNavigate('overview'),350)}} onDoubleClick={e=>{e.preventDefault();if(brandClick.current)clearTimeout(brandClick.current);onDeveloper()}}><img className="brand-word" src="/brand/maingau-wordmark-white.png" alt="MAINGAU"/><img className="brand-mark" src="/brand/maingau-mark.png" alt="" aria-hidden="true"/></a>
  <div className="brand-sub">NEXT BEST ACTION</div><div className="nav-label">WORKSPACE</div>
  <nav id="workspace-navigation" aria-label="Main navigation">{items.map(([key,label,Icon])=><button key={key} className={'nav-item'+(view===key?' active':'')} aria-label={label} aria-current={view===key?'page':undefined} title={collapsed?label:undefined} onClick={()=>onNavigate(key)}><Icon size={18} aria-hidden="true"/><span className="nav-copy">{label}</span></button>)}</nav>
  <div className="sidebar-bottom workspace-mode"><span>Demo workspace</span><small>No messages are sent</small></div>
  <button className="developer-entry" aria-label="Open Developer area" title="Developer area" onClick={onDeveloper}><Code2 size={15} aria-hidden="true"/><span>Developer area</span></button>
  {/* Always visible, in a fixed place: a control that only appears on hover is not discoverable. */}
  <button className="sidebar-toggle" aria-label={collapsed?'Expand navigation':'Collapse navigation'} title={collapsed?'Expand navigation':'Collapse navigation'} aria-expanded={!collapsed} aria-controls="workspace-navigation" onClick={toggle}>{collapsed?<PanelLeftOpen size={16} aria-hidden="true"/>:<PanelLeftClose size={16} aria-hidden="true"/>}<span className="nav-copy">Collapse</span></button>
 </aside>
}
