import {afterAll,afterEach,beforeAll,beforeEach,describe,expect,it,vi} from 'vitest';
import {cleanup,render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DeveloperArea from '../components/DeveloperArea';

const request=vi.fn();
vi.mock('../api',()=>({request:(...args:unknown[])=>request(...args)}));
vi.mock('../staticApi',()=>({STATIC_MODE:false}));
vi.mock('../pages/Method',()=>({default:()=>null}));
const connection={configured:true,session_configured:true,server_configured:false,source:'browser_session',model:'fixture',base_url:'https://example.invalid/v1',expires_in_hours:8};

const dialogMethods=['showModal','close'] as const;
const originals=dialogMethods.map(name=>Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype,name));
beforeAll(()=>{
 Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(this:HTMLDialogElement){this.open=true}});
 Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function(this:HTMLDialogElement){this.open=false}});
});
afterAll(()=>{dialogMethods.forEach((name,i)=>{const original=originals[i];if(original)Object.defineProperty(HTMLDialogElement.prototype,name,original);else Reflect.deleteProperty(HTMLDialogElement.prototype,name)})});
beforeEach(()=>{
 request.mockReset().mockImplementation((path:string)=>Promise.resolve(path==='/health'?{status:'ok',customers:750}:connection));
});
afterEach(cleanup);

describe('Developer key entry',()=>{
 it('cleans pasted whitespace and invisible characters before sending, then clears the input',async()=>{
  const user=userEvent.setup(),onConfigured=vi.fn();
  render(<DeveloperArea open onClose={()=>{}} onConfigured={onConfigured} revision={0}/>);
  const input=screen.getByLabelText('API key',{exact:true});
  await user.click(input);await user.paste(' \ufeffsk-fixture- \nkey\u00a0\u200b\u2060');
  expect(input).toHaveValue('sk-fixture-key');
  expect(screen.getByText('Spaces or invisible copy characters were removed.')).toBeInTheDocument();
  await user.click(screen.getByRole('button',{name:'Save key & check access'}));
  await waitFor(()=>expect(request).toHaveBeenCalledWith('/developer/ai','POST',{api_key:'sk-fixture-key'}));
  await waitFor(()=>expect(input).toHaveValue(''));
  expect(onConfigured).toHaveBeenCalledOnce();
 });
 it('does not submit a key containing only copy whitespace',async()=>{
  const user=userEvent.setup();
  render(<DeveloperArea open onClose={()=>{}} onConfigured={()=>{}} revision={0}/>);
  await user.click(screen.getByLabelText('API key',{exact:true}));await user.paste(' \n\u200b\ufeff');
  await user.click(screen.getByRole('button',{name:'Save key & check access'}));
  expect(screen.getByRole('alert')).toHaveTextContent('Enter the API key');
  expect(request.mock.calls.some((args:unknown[])=>args[1]==='POST')).toBe(false);
 });
 it('distinguishes a configured server key from verified access',async()=>{
  request.mockImplementation((path:string)=>Promise.resolve(path==='/health'?{status:'ok',customers:750}:{...connection,session_configured:false,server_configured:true,source:'server'}));
  render(<DeveloperArea open onClose={()=>{}} onConfigured={()=>{}} revision={0}/>);
  expect(await screen.findByText('Server key is configured')).toBeInTheDocument();
  expect(screen.getByText(/Live access has not been checked here/)).toBeInTheDocument();
  expect(screen.queryByText('Server connection is available')).not.toBeInTheDocument();
 });

});
