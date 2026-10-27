import {cleanup,render,screen,within} from '@testing-library/react';
import {afterEach,describe,expect,it} from 'vitest';
import Breadcrumbs,{customerListHref} from '../components/Breadcrumbs';

afterEach(cleanup);
describe('workspace breadcrumbs',()=>{
 it('returns to the filtered list without the customer or detail tab',()=>{
  expect(customerListHref('#customers?q=Berlin&contact=sms&page=2&customer=MG-100562&tab=studio')).toBe('#customers?q=Berlin&contact=sms&page=2');
  expect(customerListHref('#customers?customer=MG-100562')).toBe('#customers');
 });
 it('shows one trail with links to overview and the filtered directory',()=>{
  location.hash='customers?city=Mainz&customer=MG-100126&tab=permissions';
  render(<Breadcrumbs view="customers" title="Customer 360°" customerId="MG-100126"/>);
  const trail=screen.getByRole('navigation',{name:'Breadcrumb'});
  expect(within(trail).getByRole('link',{name:'Overview'})).toHaveAttribute('href','#overview');
  expect(within(trail).getByRole('link',{name:'Customers'})).toHaveAttribute('href','#customers?city=Mainz');
  expect(within(trail).getByText('MG-100126')).toHaveAttribute('aria-current','page');
 });
 it('does not treat the current page as a link',()=>{
  render(<Breadcrumbs view="overview" title="Overview" customerId={null}/>);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getByText('Overview')).toHaveAttribute('aria-current','page');
 });
});
