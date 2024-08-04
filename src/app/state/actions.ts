import { createActionGroup, props } from '@ngrx/store';
import { User } from 'firebase/auth';

export const AppStateActions = createActionGroup({
  source: 'AppState',
  events: {
    'Login User': props<{ user: User }>(),
    'Logout User': props<{ user?: User }>(),
  },
});
