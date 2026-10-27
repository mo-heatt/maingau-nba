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

const segment = {key: 'No mobile contract yet · Portal pop-up', need: 'No mobile contract yet', channel: 'portal_popup', channel_label: 'Portal pop-up', customers: 122, expected_yes: 12.6, expected_gain_eur: 3483, gain_per_contact_eur: 28.55, recommended: true, included: true, tones: {sie: 85, du: 37}, languages: {de: 122}, best_time: 'Evening', examples: [], messages: {}};
const audience = {total: 750, targeted: 750, eligible: 201, contactable: 122, control: 13, expected_gain_eur: 3483, expected_yes: 12.6, left_out: [{reason: 'profiling', label: 'No profiling consent', customers: 147}], segments: [segment]};
const base = {name: 'Mobile autumn', goal: 'Win energy customers for mobile', offer: 'P-MO-01', channel: '', starts: '', ends: '', segments: [], value_tier: [], tenure: [], lines: [], city: [], created_at: '', launched_at: null, audience, insights: []};
const result = {sent: 122, seen: 84, yes: 18, yes_rate: 0.148, control: 13, control_yes: 0, control_rate: 0, uplift: 0.148, value_won_eur: 4700, expected_gain_eur: 3483};
const tracking = {...result, simulated: true, days: 3, timeline: [{day: 1, sent: 40, yes: 5, expected_yes: 4}, {day: 2, sent: 80, yes: 11, expected_yes: 8.4}, {day: 3, sent: 122, yes: 18, expected_yes: 12.6}],
  segments: [{...result, key: segment.key, label: segment.key}], channels: [{...result, key: 'portal_popup', label: 'Portal pop-up'}]};

describe('CampaignsTab', () => {
  beforeEach(() => {request.mockReset();useApi.mockReset()});

  it('shows the personal plan of a draft and launches it', async () => {
    const user = userEvent.setup(), onChanged = vi.fn(), notify = vi.fn();
    useApi.mockReturnValue({data: {items: [{...base, id: 3, status: 'draft', tracking: null}]}});
    request.mockResolvedValue({});
    render(<CampaignsTab revision={0} names={{'P-MO-01': 'Mobil S / M / L'}} onNew={() => {}} onChanged={onChanged} notify={notify} />);
    expect(screen.getByText(/personal channels/)).toBeInTheDocument();
    expect(screen.getByText('No mobile contract yet')).toBeInTheDocument();
    await user.click(screen.getByRole('button', {name: /Approve & launch/}));
    expect(request).toHaveBeenCalledWith('/campaigns/3/launch', 'POST');
    expect(notify).toHaveBeenCalledWith(expect.stringMatching(/Nothing was sent/));
  });

  it('monitors a running campaign and turns insights into a follow-up', async () => {
    const user = userEvent.setup(), notify = vi.fn();
    const insights = [{kind: 'idea', title: 'Drop “Marketing e-mail”', text: 'It does no better than the control group.', drop: 'x'}];
    useApi.mockReturnValue({data: {items: [{...base, id: 4, status: 'running', tracking, insights}]}});
    request.mockResolvedValue({});
    render(<CampaignsTab revision={0} names={{}} onNew={() => {}} onChanged={() => {}} notify={notify} />);
    expect(screen.getByRole('img', {name: /Said yes after 3 days: 18/})).toBeInTheDocument();
    expect(screen.getByRole('table', {name: 'By segment'})).toBeInTheDocument();
    expect(screen.getByText('Drop “Marketing e-mail”')).toBeInTheDocument();
    await user.click(screen.getByRole('button', {name: /Create improved follow-up/}));
    expect(request).toHaveBeenCalledWith('/campaigns/4/follow-up', 'POST');
    expect(notify).toHaveBeenCalledWith(expect.stringMatching(/follow-up/));
  });
});
