import {useEffect,useState} from 'react';
import type {CSSProperties,KeyboardEvent} from 'react';
import {Monitor,Sun,Moon} from 'lucide-react';
import {getThemePreference,setThemePreference} from '../theme';
import type {ThemePreference} from '../theme';
const options=[{value:'light',label:'Light theme',Icon:Sun},{value:'system',label:'System theme',Icon:Monitor},{value:'dark',label:'Dark theme',Icon:Moon}] as const;
export default function ThemePicker(){
 const[value,setValue]=useState(getThemePreference);
 useEffect(()=>{const update=()=>setValue(getThemePreference());window.addEventListener('storage',update);return()=>window.removeEventListener('storage',update)},[]);
 function select(next:ThemePreference){setValue(next);setThemePreference(next)}
 function keyboard(event:KeyboardEvent<HTMLButtonElement>,index:number){
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?2:(index+(event.key==='ArrowRight'?1:2))%3;
  select(options[next].value);event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus();
 }
 return <div className="theme-control" role="radiogroup" aria-label="Colour theme" style={{'--theme-index':options.findIndex(option=>option.value===value)} as CSSProperties}><span className="theme-selection" aria-hidden="true"/>{options.map(({value:option,label,Icon},index)=><button key={option} type="button" role="radio" aria-label={label} aria-checked={value===option} title={option==='system'?'System theme · follows your device':label} tabIndex={value===option?0:-1} onClick={()=>select(option)} onKeyDown={event=>keyboard(event,index)}><Icon size={16} strokeWidth={1.7} aria-hidden="true"/></button>)}</div>;
}
