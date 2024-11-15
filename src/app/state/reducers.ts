import { createReducer, on } from '@ngrx/store';
import { initAppState } from './state';
import { AppStateActions } from './actions';

export const appStateReducer = createReducer(
  initAppState,
  on(AppStateActions.loginUser, (state, { user }) => ({
    ...state,
    user,
  })),
  on(AppStateActions.logoutUser, (state, {}) => ({
    ...state,
    user: undefined,
  })),
  on(AppStateActions.toggleLoadingAuth, (state, { loadingAuth }) => ({
    ...state,
    loadingAuth,
  })),
  on(AppStateActions.setGeminiKey, (state, { geminiKey }) => ({
    ...state,
    geminiKey,
  })),
  on(AppStateActions.addChatHistory, (state, { message }) => ({
    ...state,
    chatHistory: [...(state.chatHistory || []), message],
  })),
  on(AppStateActions.clearChatHistory, (state, {}) => ({
    ...state,
    chatHistory: [],
  })),
  on(AppStateActions.setChatContext, (state, { context }) => ({
    ...state,
    chatContext: context,
  }))
);
