import { createReducer, on } from '@ngrx/store';
import { initAppState } from './state';
import { AppStateActions } from './actions';

export const appStateReducer = createReducer(
  initAppState,
  on(AppStateActions.loginUser, (state, { user }) => ({ ...state, user })),
  on(AppStateActions.logoutUser, (state, {}) => ({
    ...state,
    user: undefined,
  }))
);
