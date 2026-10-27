import {describe, expect, it, vi} from 'vitest';
import {render, screen, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BusinessLines from '../components/BusinessLines';
import type {Customer} from '../types';

const items = [
  {id: 'energy_contracts:EN-1', category: 'electricity', name: 'StromAktiv', provider: 'MAINGAU', status: 'active', source: 'energy_contracts', source_ref: 'EN-1', details: {monthly_eur: 89.9}, relationship: 'contract', external: false},
  {id: 'shop_orders:SO-1', category: 'shop', name: 'Wallbox 11 kW', provider: 'MAINGAU', status: 'delivered', source: 'shop_orders', source_ref: 'SO-1', details: {quantity: 1}, relationship: 'purchase_record', external: false},
  {id: 'shop_orders:SO-2', category: 'shop', name: 'Smart Plug 4er-Set', provider: 'MAINGAU', status: 'delivered', source: 'shop_orders', source_ref: 'SO-2', details: {quantity: 2}, relationship: 'purchase_record', external: false},
];

const customer = {
  id: 'MG-100562',
  decision: {action: 'none'},
  candidates: [],
  products: [{line: 'energy', name: 'StromAktiv', status: 'active'}],
} as unknown as Customer;

vi.mock('../api', () => ({
  useApi: () => ({data: {items}, error: '', loading: false}),
  eur: (v: number) => v.toFixed(2) + ' €',
}));

describe('BusinessLines', () => {
  it('renders every MAINGAU business line', () => {
    render(<BusinessLines c={customer} revision={0} />);
    for (const label of ['Energy', 'Autostrom', 'Mobile', 'Internet', 'Smart Living', 'Online shop']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('expands the product list of a business line on click and collapses it again', async () => {
    const user = userEvent.setup();
    render(<BusinessLines c={customer} revision={0} />);
    expect(screen.queryByText('Wallbox 11 kW')).not.toBeInTheDocument();
    const energyToggle = screen.getByRole('button', {name: /Energy/});
    expect(energyToggle).toHaveAttribute('aria-expanded', 'false');
    await user.click(energyToggle);
    expect(energyToggle).toHaveAttribute('aria-expanded', 'true');
    const panel = document.querySelector('.line-products') as HTMLElement;
    expect(within(panel).getByText('StromAktiv')).toBeInTheDocument();
    expect(within(panel).getByText('89.90 € / month')).toBeInTheDocument();
    await user.click(energyToggle);
    expect(energyToggle).toHaveAttribute('aria-expanded', 'false');
    expect(document.querySelector('.line-products')).toBeNull();
  });

  it('shows all products together via "Show all products"', async () => {
    const user = userEvent.setup();
    render(<BusinessLines c={customer} revision={0} />);
    await user.click(screen.getByRole('button', {name: 'Show all products'}));
    expect(document.querySelectorAll('.line-products')).toHaveLength(2);
    expect(screen.getByText('Wallbox 11 kW')).toBeInTheDocument();
    expect(screen.getByText('Smart Plug 4er-Set')).toBeInTheDocument();
  });

  it('links an in-use product to the MAINGAU website and opens the detail page', async () => {
    const user = userEvent.setup();
    render(<BusinessLines c={customer} revision={0} />);
    await user.click(screen.getByRole('button', {name: /Online shop/}));
    await user.click(screen.getAllByRole('button', {name: 'Details'})[0]);
    const dialog = screen.getByRole('dialog', {name: /Wallbox 11 kW details/});
    expect(within(dialog).getByText('Wallbox 11 kW')).toBeInTheDocument();
    expect(within(dialog).getByText('MAINGAU Onlineshop')).toHaveAttribute('href', 'https://www.maingau-energie.de/onlineshop');
    await user.click(within(dialog).getByRole('button', {name: 'Close product details'}));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('keeps unused lines static with their gap explanation', () => {
    render(<BusinessLines c={customer} revision={0} />);
    const mobile = screen.getByText('Mobile').closest('.line-card') as HTMLElement;
    expect(mobile.className).not.toContain('in-use');
    expect(mobile.querySelector('button.line-head')).toBeNull();
    expect(within(mobile).getByText(/Not in use/)).toBeInTheDocument();
  });
});
