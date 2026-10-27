import {describe, expect, it, vi, beforeEach} from 'vitest';
import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AssistantChat from '../components/AssistantChat';

vi.mock('../staticApi', () => ({STATIC_MODE: false}));

const request = vi.fn();
vi.mock('../api', () => ({request: (...args: unknown[]) => request(...args)}));

describe('AssistantChat', () => {
  beforeEach(() => {request.mockReset()});

  it('sends the conversation and links customer IDs in the answer', async () => {
    const user = userEvent.setup(), onSelect = vi.fn();
    request.mockResolvedValue({answer: 'MG-100004 has an open complaint, so service comes first.'});
    render(<AssistantChat onSelect={onSelect} onConnect={() => {}} />);
    await user.click(screen.getByRole('button', {name: 'Ask the data assistant'}));
    await user.type(screen.getByRole('textbox', {name: 'Question'}), 'Why no offer for MG-100004?{Enter}');
    expect(request).toHaveBeenCalledWith('/assistant', 'POST', {messages: [{role: 'user', content: 'Why no offer for MG-100004?'}]});
    await user.click(await screen.findByRole('button', {name: 'MG-100004'}));
    expect(onSelect).toHaveBeenCalledWith('MG-100004');
  });

  it('offers the Developer area when no AI key is connected', async () => {
    const user = userEvent.setup(), onConnect = vi.fn();
    request.mockRejectedValue(Error('Connect Hessian AI in the Developer area to ask questions.'));
    render(<AssistantChat onSelect={() => {}} onConnect={onConnect} />);
    await user.click(screen.getByRole('button', {name: 'Ask the data assistant'}));
    await user.click(screen.getByRole('button', {name: 'Which offer is recommended most often?'}));
    await user.click(await screen.findByRole('button', {name: 'Open Developer area'}));
    expect(onConnect).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole('button', {name: 'Send'})).toBeDisabled());
  });
});
