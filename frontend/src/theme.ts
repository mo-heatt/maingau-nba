export type ThemePreference = 'system' | 'light' | 'dark';
const key='maingau-theme';
const system=window.matchMedia('(prefers-color-scheme: dark)');
function readPreference():ThemePreference{
 try{const saved=localStorage.getItem(key);if(saved==='light'||saved==='dark')return saved}catch{/* Keep a session preference if storage is unavailable. */}
 return 'system';
}
let preference=readPreference();
export const getThemePreference=()=>preference;
function apply(){document.documentElement.dataset.theme=preference==='system'?(system.matches?'dark':'light'):preference}
export function setThemePreference(next:ThemePreference){
 preference=next;
 try{localStorage.setItem(key,next)}catch{/* The in-memory preference still works. */}
 apply();
}
apply();
system.addEventListener('change',()=>{if(preference==='system')apply()});
window.addEventListener('storage',event=>{if(event.key===key||event.key===null){preference=readPreference();apply()}});
