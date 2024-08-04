import { User } from 'firebase/auth';

export interface AppState {
  user?: User;
}

export const initAppState: AppState = {
  user: undefined,
};
