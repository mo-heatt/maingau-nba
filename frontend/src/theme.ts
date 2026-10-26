export type ThemePreference = 'system' | 'light' | 'dark';
const key = 'maingau-theme';
const system = window.matchMedia('(prefers-color-scheme: dark)');
export function getThemePreference(): ThemePreference {
 try { const saved = localStorage.getItem(key); if (saved === 'light' || saved === 'dark') return saved; } catch { /* System theme works when storage is unavailable. */ }
 return 'system';
}
function apply(preference: ThemePreference) {
 document.documentElement.dataset.theme = preference === 'system' ? (system.matches ? 'dark' : 'light') : preference;
}
export function setThemePreference(preference: ThemePreference) {
 try { localStorage.setItem(key, preference); } catch { /* Keep the current session usable. */ }
 apply(preference);
}
apply(getThemePreference());
system.addEventListener('change', () => { if (getThemePreference() === 'system') apply('system'); });

window.addEventListener('storage', event => { if (event.key === key || event.key === null) apply(getThemePreference()); });
