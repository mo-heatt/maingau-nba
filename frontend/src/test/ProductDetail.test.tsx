import {describe, expect, it, vi} from 'vitest';
import {render, screen, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ProductDetail from '../components/ProductDetail';

vi.mock('../staticApi', () => ({STATIC_MODE: false}));
vi.mock('../api', () => ({
  eur: (v: number) => v.toFixed(2) + ' €',
  request: vi.fn(),
  useApi: () => ({data: null, error: '', loading: false}),
}));

const contract = {id: 'energy_contracts:EN-1', category: 'electricity', name: 'StromAktiv', provider: 'MAINGAU', status: 'active', source: 'energy_contracts', source_ref: 'EN-500669', relationship: 'contract', external: false, details: {unit_eur_kwh: 0.329, base_eur_month: 12.9, annual_kwh: 2262, price_guarantee_until: '2026-04-07'}};

describe('ProductDetail', () => {
  it('shows every recorded product fact in human form plus the source', () => {
    render(<ProductDetail cid="MG-100562" product={contract} onClose={() => {}} />);
    const dialog = screen.getByRole('dialog', {name: 'StromAktiv details'});
    expect(within(dialog).getByText('0,329 € / kWh')).toBeInTheDocument();
    expect(within(dialog).getByText('12.90 € / month base')).toBeInTheDocument();
    expect(within(dialog).getByText('2.262 kWh / year')).toBeInTheDocument();
    expect(within(dialog).getByText('7 Apr 2026')).toBeInTheDocument();
    expect(within(dialog).getByText(/energy_contracts · EN-500669/)).toBeInTheDocument();
  });

  it('links the MAINGAU product page for own products and closes on backdrop click and Escape', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const {rerender, container} = render(<ProductDetail cid="MG-100562" product={contract} onClose={onClose} />);
    expect(screen.getByText('MAINGAU Stromtarife')).toHaveAttribute('href', 'https://www.maingau-energie.de/strom');
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
    rerender(<ProductDetail cid="MG-100562" product={contract} onClose={onClose} />);
    await user.click(container.querySelector('.product-detail-backdrop')!);
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('offers no product page link for an external provider record', () => {
    const external = {...contract, external: true, provider: 'Provider not named', relationship: 'competing_offer'};
    render(<ProductDetail cid="MG-100562" product={external} onClose={() => {}} />);
    expect(screen.queryByRole('link', {name: /MAINGAU/})).not.toBeInTheDocument();
  });
});
