import { User } from '.';

export interface AppState {
  user?: User;
}

export const initAppState: AppState = {
  user: undefined,
};
