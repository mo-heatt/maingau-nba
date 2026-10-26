// Online demo mode: the app reads a snapshot of every server answer instead of calling FastAPI.
// Built with VITE_STATIC=1; the snapshot is embedded in the page as gzip+base64 (window.__SNAP_GZ).
type Snap = Record<string, any>;
declare global { interface Window { __SNAP_GZ?: string } }

let snap: Promise<Snap> | null = null;

async function load(): Promise<Snap> {
  const b64 = window.__SNAP_GZ || '';
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  return JSON.parse(await new Response(stream).text());
}

const READ_ONLY = 'This online demo is read-only. Run the full app to change rules or generate AI drafts.';

export async function staticRequest<T>(path: string, method = 'GET', body?: any): Promise<T> {
  const S = await (snap ||= load());
  const [route, query = ''] = path.split('?');
  const p = new URLSearchParams(query);

  if (method === 'GET') {
    if (route === '/customers') {
      const q = (p.get('q') || '').toLowerCase(), action = p.get('action') || '';
      const offset = +(p.get('offset') || 0), limit = +(p.get('limit') || 50);
      const rows = (S.__list as any[]).filter(r => (r.id + ' ' + r.city).toLowerCase().includes(q) && (!action || r.decision.action === action));
      return {total: rows.length, offset, limit, items: rows.slice(offset, offset + limit)} as T;
    }
    if (route in S) return structuredClone(S[route]) as T;
    if (route.endsWith('/outreach')) return {items: []} as T;
    throw Error(READ_ONLY);
  }

  // Approvals work for this browser session so the flow can be demoed; nothing is sent or saved.
  const review = route.match(/^\/customers\/([^/]+)\/reviews$/);
  if (method === 'POST' && review) {
    const id = review[1], status = body?.status || 'approved';
    const set = (d: any) => { if (d) d.status = status; };
    set(S['/customers/' + id]?.decision);
    set((S.__list as any[]).find(r => r.id === id)?.decision);
    const m = S['/marketing'];
    set(m?.queue?.find((r: any) => r.id === id)?.decision);
    if (m && status === 'approved') m.approved = (m.approved || 0) + 1;
    return {ok: true} as T;
  }
  throw Error(READ_ONLY);
}

export const STATIC_MODE = !!import.meta.env.VITE_STATIC;
