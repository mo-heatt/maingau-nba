import {createContext,useCallback,useContext,useState} from 'react';
import type {ReactNode} from 'react';
import type {Latest} from './AIDecision';
import {useApi} from '../api';
const Context=createContext<{data:Latest|null;error:string;loading:boolean;refresh:()=>void}>({data:null,error:'',loading:true,refresh:()=>{}});
export function CustomerDecisionProvider({id,revision,children}:{id:string;revision:number;children:ReactNode}){
 const[tick,setTick]=useState(0),state=useApi<Latest>('/customers/'+id+'/ai-nba',revision+tick);
 const refresh=useCallback(()=>setTick(v=>v+1),[]);
 return <Context.Provider value={{...state,data:state.loading?null:state.data,refresh}}>{children}</Context.Provider>;
}
export const useCustomerDecision=()=>useContext(Context);
