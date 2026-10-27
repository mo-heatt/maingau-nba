export type ThemePreference = 'light' | 'dark';
const key='maingau-theme';
function readPreference():ThemePreference{
 try{const saved=localStorage.getItem(key);if(saved==='light'||saved==='dark')return saved}catch{/* Keep a session preference if storage is unavailable. */}
 return 'light';
}
let preference=readPreference();
export const getThemePreference=()=>preference;
function apply(){document.documentElement.dataset.theme=preference}
export function setThemePreference(next:ThemePreference){
 preference=next;
 try{localStorage.setItem(key,next)}catch{/* The in-memory preference still works. */}
 apply();
}
apply();
window.addEventListener('storage',event=>{if(event.key===key||event.key===null){preference=readPreference();apply()}});
