import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { Agent } from 'node:http';
// uvicorn closes idle connections after 5 s; a reused socket then fails with ECONNRESET and the
// browser request never settles. Use a fresh connection per request and answer proxy errors with 502.
export default defineConfig({plugins:[react()],server:{port:5173,proxy:{'/api':{target:'http://127.0.0.1:8001',agent:new Agent({keepAlive:false}),
 configure:proxy=>proxy.on('error',(err,_req,res)=>{if('writeHead' in res&&!res.headersSent){res.writeHead(502,{'Content-Type':'application/json'});res.end(JSON.stringify({detail:'The backend could not be reached ('+err.message+').'}))}})}}}});
