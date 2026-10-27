import {afterEach,describe,expect,it} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import {QuoteCard,type Quote} from '../components/OutreachWorkbench';
import type {Product} from '../types';

afterEach(cleanup);
const product:Product={product_id:'P-MO-02',product_name:'Mobil Upgrade',business_line:'mobile',action_type:'upsell',description:'Mehr Datenvolumen'};
const quote:Quote={id:'q1',product_id:'P-MO-02',product_name:'Mobil Upgrade',demo:true,current:{name:'Mobil S',data_gb:10,monthly_eur:9.99},target:{name:'Mobil M',data_gb:30,monthly_eur:14.99},delta_monthly_eur:5,missing:[],terms:[]};

describe('Customer-facing offer language',()=>{
 it('uses English labels and benefits while preserving actual tariff names and prices',()=>{
  render(<QuoteCard quote={quote} product={product} tone="du" language="en" onInterest={()=>{}}/>);
  expect(screen.getByText('Selected for you')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Save this offer'})).toBeInTheDocument();
  expect(screen.getByText('Current')).toBeInTheDocument();
  expect(screen.getAllByText('Mobil M').length).toBeGreaterThan(0);
  expect(screen.getByText('More mobile data by moving to the next tariff tier.')).toBeInTheDocument();
  expect(screen.queryByText('Für dich ausgewählt')).not.toBeInTheDocument();
  expect(screen.getByText(/Demo tariff from supplied data/)).toBeInTheDocument();
 });
 it('retains German copy for a German customer',()=>{
  render(<QuoteCard quote={quote} product={product} tone="sie" language="de"/>);
  expect(screen.getByText('Für Sie ausgewählt')).toBeInTheDocument();
  expect(screen.getByText('Aktuell')).toBeInTheDocument();
 });
});
