import {useEffect,useState} from 'react';
import type {CSSProperties,KeyboardEvent} from 'react';
import {Sun,Moon} from 'lucide-react';
import {getThemePreference,setThemePreference} from '../theme';
import type {ThemePreference} from '../theme';
const options=[{value:'light',label:'Light',Icon:Sun},{value:'dark',label:'Dark',Icon:Moon}] as const;
export default function ThemePicker(){
 const[value,setValue]=useState(getThemePreference);
 useEffect(()=>{const update=()=>setValue(getThemePreference());window.addEventListener('storage',update);return()=>window.removeEventListener('storage',update)},[]);
 function select(next:ThemePreference){setValue(next);setThemePreference(next)}
 function keyboard(event:KeyboardEvent<HTMLButtonElement>,index:number){
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?1:(index+1)%2;
  select(options[next].value);event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus();
 }
 return <div className="theme-control" role="radiogroup" aria-label="Colour theme" style={{'--theme-index':options.findIndex(option=>option.value===value)} as CSSProperties}><span className="theme-selection" aria-hidden="true"/>{options.map(({value:option,label,Icon},index)=><button key={option} type="button" role="radio" aria-label={label+' theme'} aria-checked={value===option} title={label+' theme'} tabIndex={value===option?0:-1} onClick={()=>select(option)} onKeyDown={event=>keyboard(event,index)}><Icon size={15} strokeWidth={1.8} aria-hidden="true"/><span>{label}</span></button>)}</div>;
}
