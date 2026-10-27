import {describe, expect, it, vi, beforeEach} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CustomerChat from '../components/CustomerChat';
import type {Customer} from '../types';

vi.mock('../staticApi', () => ({STATIC_MODE: false}));

const request = vi.fn();
vi.mock('../api', () => ({request: (...args: unknown[]) => request(...args)}));

const customer = {id: 'MG-100562', tone: 'du', open_tickets: [{ticket_id: 'TK-1'}], decision: {action: 'service', name: 'Proactive service fix'}} as unknown as Customer;

describe('CustomerChat', () => {
  beforeEach(() => {request.mockReset()});

  it('asks about this customer only and offers questions that fit the profile', async () => {
    const user = userEvent.setup();
    request.mockResolvedValue({answer: '**In short**\nCall back today.'});
    render(<CustomerChat customer={customer} onSelect={() => {}} onConnect={() => {}} />);
    expect(screen.getByRole('button', {name: 'How do I solve the open problem in the next call?'})).toBeInTheDocument();
    await user.click(screen.getByRole('button', {name: 'What is going on with this customer?'}));
    expect(request).toHaveBeenCalledWith('/assistant', 'POST', {messages: [{role: 'user', content: 'What is going on with this customer?'}], customer_id: 'MG-100562'});
    expect(await screen.findByRole('heading', {name: 'In short'})).toBeInTheDocument();
  });
});
