import { User, HistoryMessage, ChatContext } from '.';

export interface AppState {
  user?: User;
  loadingAuth?: boolean;
  geminiKey?: string;
  chatHistory?: HistoryMessage[];
  chatContext?: ChatContext;
}

export const initAppState: AppState = {
  user: undefined,
  loadingAuth: false,
  geminiKey: '',
  chatHistory: [],
  chatContext: undefined,
};
