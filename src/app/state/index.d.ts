export interface User {
  uid: string;
  displayName?: string;
  photoURL?: string;
  email?: string;
}

export interface HistoryMessage {
  role: string;
  message: string;
}

export interface ChatContext {
  content: string;
  query: string;
  filter: string;
  loaded: boolean;
}
