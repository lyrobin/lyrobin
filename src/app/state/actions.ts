import { createActionGroup, props } from '@ngrx/store';
import { User } from '.';

export const AppStateActions = createActionGroup({
  source: 'AppState',
  events: {
    'Login User': props<{ user: User }>(),
    'Logout User': props<{ user?: User }>(),
  },
});
