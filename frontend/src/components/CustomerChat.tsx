import {useRef} from 'react';
import {Sparkles} from 'lucide-react';
import {ChatInput, ChatThread, useAssistant} from './AssistantChat';
import type {Customer} from '../types';

// Questions that fit what this customer's profile shows, so the first click is already useful.
function suggestions(c: Customer) {
  const out = ['What is going on with this customer?'];
  if (c.open_tickets.length) out.push('What did the customer say in their last contact, and what was promised?');
  if (c.decision.action === 'offer') out.push(`Why ${c.decision.name}, and how should I bring it up?`);
  else if (c.decision.action === 'service') out.push('How do I solve the open problem in the next call?');
  else out.push('Why is the engine not contacting this customer?');
  out.push(`Suggest an opening sentence for a call (${c.tone === 'du' ? 'Du' : 'Sie'}).`);
  return out.slice(0, 3);
}

// A chat about this one customer, in the middle of their profile. The server only sees this customer.
export default function CustomerChat({customer, onSelect, onConnect}: {customer: Customer; onSelect: (id: string) => void; onConnect: () => void}) {
  const chat = useAssistant(customer.id), list = useRef<HTMLDivElement>(null);
  return <section className="customer-chat" aria-label={'Chat about ' + customer.id}>
    <header><Sparkles size={16} aria-hidden="true" /><h2>Ask about {customer.id}</h2><span>Uses this customer's calls, contracts, tickets and consent</span></header>
    <ChatThread chat={chat} listRef={list} intro="Ask anything about this customer, or tell me what they just said." suggestions={suggestions(customer)} onSelect={onSelect} onConnect={onConnect} />
    <ChatInput chat={chat} placeholder={`Ask about ${customer.id}…`} />
    <small className="assistant-note">AI answers from this customer's mock data and can be wrong. Nothing is sent or changed.</small>
  </section>;
}
