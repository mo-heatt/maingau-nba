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

  it('shows answers with headings and bullet points', async () => {
    const user = userEvent.setup();
    request.mockResolvedValue({answer: '**In short**\nMG-100562 is upset and was promised a **callback**.\n\n**What to do now**\n- Call back today\n- Book the promised credit note'});
    render(<AssistantChat onSelect={() => {}} onConnect={() => {}} />);
    await user.click(screen.getByRole('button', {name: 'Ask the data assistant'}));
    await user.type(screen.getByRole('textbox', {name: 'Question'}), 'Was ist mit MG-100562?{Enter}');
    expect(await screen.findByRole('heading', {name: 'What to do now'})).toBeInTheDocument();
    expect(screen.getAllByRole('listitem').map(li => li.textContent)).toEqual(['Call back today', 'Book the promised credit note']);
    expect(screen.getByText('callback').tagName).toBe('B');
    expect(screen.getByRole('button', {name: 'MG-100562'})).toBeInTheDocument();
  });
});
