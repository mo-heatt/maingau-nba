import {describe, expect, it, vi, beforeEach} from 'vitest';
import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UpgradeIdeas from '../components/UpgradeIdeas';

vi.mock('../staticApi', () => ({STATIC_MODE: false}));

const request = vi.fn();
vi.mock('../api', () => ({request: (...args: unknown[]) => request(...args)}));

const product = {id: 'mobile_contracts:MO-1', category: 'mobile', name: 'Mobil M', provider: 'MAINGAU', status: 'active', details: {data_gb: 5}};

describe('UpgradeIdeas', () => {
  beforeEach(() => {request.mockReset()});

  it('loads and shows exactly three AI upgrade ideas with the MAINGAU link', async () => {
    const user = userEvent.setup();
    request.mockResolvedValue({ideas: [
      {title: 'Pay for less data', problem: '5 GB may exceed actual usage.', benefit: 'A smaller tier can reduce the monthly fee.'},
      {title: 'More data volume', problem: 'Streaming pushes the plan to its limit.', benefit: 'The next stage avoids throttling.'},
      {title: 'Additional SIM', problem: 'Family members are on separate contracts.', benefit: 'One bundled contract is easier to manage.'},
    ], source: 'ai', note: null});
    render(<UpgradeIdeas cid="MG-100562" product={product} />);
    await user.click(screen.getByRole('button', {name: /Upgrade ideas/}));
    expect(request).toHaveBeenCalledWith('/customers/MG-100562/upgrade-ideas', 'POST', expect.objectContaining({product_id: 'mobile_contracts:MO-1', category: 'mobile', name: 'Mobil M'}));
    await waitFor(() => expect(screen.getByText('More data volume')).toBeInTheDocument());
    const cards = screen.getAllByText(/Benefit:/);
    expect(cards).toHaveLength(3);
    expect(screen.getByText('MAINGAU Mobilfunktarife')).toHaveAttribute('href', 'https://www.maingau-energie.de/mobilfunk');
  });

  it('shows the error message when the request fails', async () => {
    const user = userEvent.setup();
    request.mockRejectedValue(new Error('AI provider unavailable'));
    render(<UpgradeIdeas cid="MG-100562" product={product} />);
    await user.click(screen.getByRole('button', {name: /Upgrade ideas/}));
    await waitFor(() => expect(screen.getByText('AI provider unavailable')).toBeInTheDocument());
  });
});
