import {describe, expect, it, vi, beforeEach} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {CampaignsTab} from '../components/Campaigns';

vi.mock('../staticApi', () => ({STATIC_MODE: false}));

const request = vi.fn(), useApi = vi.fn();
vi.mock('../api', () => ({
  request: (...args: unknown[]) => request(...args),
  useApi: (...args: unknown[]) => useApi(...args),
  eur: (v: number) => v + ' €',
  channel: (c: string) => c,
}));

const audience = {total: 750, targeted: 150, contactable: 10, control: 7, expected_gain_eur: 693.14, expected_yes: 1.5, left_out: [{reason: 'profiling', label: 'No profiling consent', customers: 14}]};
const base = {name: 'Autumn StromGarant', offer: 'P-EN-02', channel: 'newsletter_email', starts: '', ends: '', value_tier: ['High value (top 20 %)'], tenure: [], lines: [], city: [], created_at: '', launched_at: null, audience};

describe('CampaignsTab', () => {
  beforeEach(() => {request.mockReset();useApi.mockReset()});

  it('launches a draft and reports that nothing is sent', async () => {
    const user = userEvent.setup(), onChanged = vi.fn(), notify = vi.fn();
    useApi.mockReturnValue({data: {items: [{...base, id: 3, status: 'draft', tracking: null}]}});
    request.mockResolvedValue({});
    render(<CampaignsTab revision={0} names={{'P-EN-02': 'StromGarant'}} onNew={() => {}} onChanged={onChanged} notify={notify} />);
    expect(screen.getByText('No profiling consent')).toBeInTheDocument();
    await user.click(screen.getByRole('button', {name: /Approve & launch/}));
    expect(request).toHaveBeenCalledWith('/campaigns/3/launch', 'POST');
    expect(onChanged).toHaveBeenCalled();
    expect(notify).toHaveBeenCalledWith(expect.stringMatching(/Nothing was sent/));
  });

  it('shows simulated tracking with the control group for a running campaign', () => {
    useApi.mockReturnValue({data: {items: [{...base, id: 4, status: 'running', tracking: {simulated: true, sent: 10, seen: 3, yes: 1, control: 7, control_yes: 0, yes_rate: 0.1, control_rate: 0, uplift: 0.1, value_won_eur: 318.7}}]}});
    render(<CampaignsTab revision={0} names={{}} onNew={() => {}} onChanged={() => {}} notify={() => {}} />);
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('+10,0 pts')).toBeInTheDocument();
    expect(screen.getByText(/Simulated results/)).toBeInTheDocument();
  });
});
