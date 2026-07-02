import { create } from 'zustand';
import { queryApi } from '../api/client';
import type { ChatMessage, ClarificationResult, AnswerResult } from '../api/types';

interface QueryState {
  conversations: ChatMessage[];
  pendingQuestion: string;
  isQuerying: boolean;

  submitQuery: (question: string) => Promise<void>;
  respondToQuestion: (queryId: string, answer: string) => Promise<void>;
  clearConversation: () => void;
}

function createId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export const useQueryStore = create<QueryState>((set, get) => ({
  conversations: [],
  pendingQuestion: '',
  isQuerying: false,

  submitQuery: async (question: string) => {
    const userMsg: ChatMessage = {
      id: createId(),
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    };

    set((s) => ({
      conversations: [...s.conversations, userMsg],
      pendingQuestion: question,
      isQuerying: true,
    }));

    try {
      const result = await queryApi.submit(question);

      if (result.type === 'clarification') {
        const clarification = result as ClarificationResult;
        const clarMsg: ChatMessage = {
          id: createId(),
          role: 'clarification',
          content: clarification.question,
          timestamp: new Date().toISOString(),
          clarification,
        };
        set((s) => ({
          conversations: [...s.conversations, clarMsg],
          isQuerying: false,
        }));
      } else {
        const answer = result as AnswerResult;
        const answerMsg: ChatMessage = {
          id: createId(),
          role: 'assistant',
          content: answer.summary,
          timestamp: new Date().toISOString(),
          result: answer,
        };
        set((s) => ({
          conversations: [...s.conversations, answerMsg],
          isQuerying: false,
          pendingQuestion: '',
        }));
      }
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: createId(),
        role: 'assistant',
        content: `Error: ${(err as Error).message}`,
        timestamp: new Date().toISOString(),
      };
      set((s) => ({
        conversations: [...s.conversations, errorMsg],
        isQuerying: false,
      }));
    }
  },

  respondToQuestion: async (queryId: string, answer: string) => {
    const userMsg: ChatMessage = {
      id: createId(),
      role: 'user',
      content: answer,
      timestamp: new Date().toISOString(),
    };

    set((s) => ({
      conversations: [...s.conversations, userMsg],
      isQuerying: true,
    }));

    try {
      const result = await queryApi.respond(queryId, answer);

      if (result.type === 'answer') {
        const answerResult = result as AnswerResult;
        const answerMsg: ChatMessage = {
          id: createId(),
          role: 'assistant',
          content: answerResult.summary,
          timestamp: new Date().toISOString(),
          result: answerResult,
        };
        set((s) => ({
          conversations: [...s.conversations, answerMsg],
          isQuerying: false,
          pendingQuestion: '',
        }));
      }
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: createId(),
        role: 'assistant',
        content: `Error: ${(err as Error).message}`,
        timestamp: new Date().toISOString(),
      };
      set((s) => ({
        conversations: [...s.conversations, errorMsg],
        isQuerying: false,
      }));
    }
  },

  clearConversation: () =>
    set({ conversations: [], pendingQuestion: '', isQuerying: false }),
}));
