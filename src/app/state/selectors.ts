import { createFeatureSelector, createSelector } from '@ngrx/store';
import { AppState } from './state';

export const selectAppState = createFeatureSelector<AppState>('appState');
export const selectUser = createSelector(selectAppState, state => state.user);
export const isUserLoggedIn = createSelector(
  selectAppState,
  state => state.user !== undefined
);
