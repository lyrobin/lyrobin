import { createActionGroup, props } from '@ngrx/store';
import { ChatContext, HistoryMessage, User } from '.';

export const AppStateActions = createActionGroup({
  source: 'AppState',
  events: {
    'Login User': props<{ user: User }>(),
    'Logout User': props<{ user?: User }>(),
    'Toggle Loading Auth': props<{ loadingAuth: boolean }>(),
    'Set Gemini Key': props<{ geminiKey: string }>(),
    'Add Chat History': props<{ message: HistoryMessage }>(),
    'Clear Chat History': props<{ _: undefined }>(),
    'Set Chat Context': props<{ context: ChatContext }>(),
  },
});
