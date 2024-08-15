import { User } from '.';

export interface AppState {
  user?: User;
  loadingAuth?: boolean;
}

export const initAppState: AppState = {
  user: undefined,
  loadingAuth: false,
};
