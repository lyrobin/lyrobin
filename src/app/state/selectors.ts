import { createFeatureSelector, createSelector } from '@ngrx/store';
import { AppState } from './state';

export const selectAppState = createFeatureSelector<AppState>('appState');
export const selectUser = createSelector(selectAppState, state => state.user);
export const isUserLoggedIn = createSelector(
  selectAppState,
  state => state.user !== undefined
);
export const isLoadingAuth = createSelector(
  selectAppState,
  state => state.loadingAuth
);
export const selectGeminiKey = createSelector(
  selectAppState,
  state => state.geminiKey
);
export const selectChatHistory = createSelector(
  selectAppState,
  state => state.chatHistory
);
export const selectChatContext = createSelector(
  selectAppState,
  state => state.chatContext
);
