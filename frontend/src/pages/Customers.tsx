import {useLayoutEffect,useRef} from 'react';
import CustomerDirectory from './CustomerDirectory';
import Customer360 from './Customer360';
export default function Customers({id,onSelect,onBack,revision,onChanged,notify}:{id:string|null;onSelect:(id:string)=>void;onBack:()=>void;revision:number;onChanged:()=>void;notify:(message:string)=>void}){
 const directoryScroll=useRef(0);
 useLayoutEffect(()=>{window.scrollTo({top:id?0:directoryScroll.current,behavior:'instant'})},[id]);
 const select=(next:string)=>{directoryScroll.current=window.scrollY;onSelect(next)};
 return <><div hidden={id!==null}><CustomerDirectory active={id===null} revision={revision} onSelect={select} onChanged={onChanged} notify={notify}/></div>{id&&<Customer360 key={id} id={id} onBack={onBack} revision={revision} onChanged={onChanged} notify={notify}/>}</>
}
