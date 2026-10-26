import {useEffect,useState} from 'react';
import {SunMoon} from 'lucide-react';
import {getThemePreference,setThemePreference} from '../theme';
import type {ThemePreference} from '../theme';
export default function ThemePicker(){
 const[value,setValue]=useState(getThemePreference);
 useEffect(()=>{const update=()=>setValue(getThemePreference());window.addEventListener('storage',update);return()=>window.removeEventListener('storage',update)},[]);
 return <label className="theme-picker"><SunMoon size={16}/><select aria-label="Colour theme" value={value} onChange={e=>{const next=e.target.value as ThemePreference;setValue(next);setThemePreference(next)}}><option value="system">System theme</option><option value="light">Light theme</option><option value="dark">Dark theme</option></select></label>;
}
