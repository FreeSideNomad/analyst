// ── query-store ───────────────────────────────────────────────────────
// Owner: Q&A surface (feature 003 owns this file).
import { create } from 'zustand';
import { api } from '../api/client';
import type { ChatMessage, ClarificationResult } from '../api/types';

let _mid = 0;
const nid = () => 'm' + ++_mid;

interface QueryState {
  messages: ChatMessage[];
  pending: ClarificationResult | null;
  thinking: boolean;
  submit: (text: string) => Promise<void>;
  respond: (payload: ClarificationResult, value: string) => Promise<void>;
}
export const useQuery = create<QueryState>((set) => ({
  messages: [],
  pending: null,
  thinking: false,
  submit: async (text) => {
    const q = text.trim();
    if (!q) return;
    set((s) => ({ messages: [...s.messages, { id: nid(), type: 'user', text: q }], thinking: true, pending: null }));
    const res = await api.submitQuery(q);
    if (res.type === 'clarification') {
      set((s) => ({ thinking: false, messages: [...s.messages, { id: nid(), type: 'clarification', payload: res, chosen: null }], pending: res }));
    } else {
      set((s) => ({ thinking: false, messages: [...s.messages, { id: nid(), type: 'result', result: res }] }));
    }
  },
  respond: async (payload, value) => {
    set((s) => ({
      messages: s.messages.map((m) => (m.type === 'clarification' && m.payload.queryId === payload.queryId ? { ...m, chosen: value } : m)),
      pending: null, thinking: true,
    }));
    const res = await api.respondQuery(payload.queryId, [value]);
    set((s) => ({ thinking: false, messages: [...s.messages, { id: nid(), type: 'result', result: res }] }));
  },
}));
