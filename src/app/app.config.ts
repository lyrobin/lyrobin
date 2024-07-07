import { ApplicationConfig, importProvidersFrom } from '@angular/core';
import {
  provideRouter,
  withComponentInputBinding,
  withInMemoryScrolling,
} from '@angular/router';

import { routes } from './app.routes';
import { provideClientHydration } from '@angular/platform-browser';
import { WINDOW, windowProvider } from './providers/window';
import { DOCUMENT } from '@angular/common';
import { initializeApp, provideFirebaseApp } from '@angular/fire/app';
import { getAuth, provideAuth } from '@angular/fire/auth';
import {
  getAnalytics,
  provideAnalytics,
  ScreenTrackingService,
  UserTrackingService,
} from '@angular/fire/analytics';
import { getFirestore, provideFirestore } from '@angular/fire/firestore';
import { getFunctions, provideFunctions } from '@angular/fire/functions';
import { getMessaging, provideMessaging } from '@angular/fire/messaging';
import { getStorage, provideStorage } from '@angular/fire/storage';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideAnimations } from '@angular/platform-browser/animations';
import { provideHttpClient } from '@angular/common/http';
import {
  provideMarkdown,
  MARKED_OPTIONS,
  MarkedOptions,
  MarkedRenderer,
} from 'ngx-markdown';

export function markedOptionsFactory(): MarkedOptions {
  const renderer = new MarkedRenderer();

  renderer.blockquote = (text: string) => {
    return '<blockquote class="blockquote"><p>' + text + '</p></blockquote>';
  };

  renderer.strong = (text: string) => {
    return '<strong>' + text + '</strong>';
  };

  return {
    renderer: renderer,
    gfm: true,
    breaks: false,
    pedantic: false,
  };
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(
      routes,
      withComponentInputBinding(),
      withInMemoryScrolling({
        scrollPositionRestoration: 'enabled',
      })
    ),
    provideClientHydration(),
    {
      provide: WINDOW,
      useFactory: (document: Document) => windowProvider(document),
      deps: [DOCUMENT],
    },
    provideFirebaseApp(() =>
      initializeApp({
        projectId: 'taiwan-legislative-search',
        appId: '1:661598081211:web:febbd559cbf3295bdb999e',
        storageBucket: 'taiwan-legislative-search.appspot.com',
        apiKey: 'AIzaSyCWElTvWiGH7rZMxFl2s5xEbsLXDo3Ub44',
        authDomain: 'taiwan-legislative-search.firebaseapp.com',
        messagingSenderId: '661598081211',
        measurementId: 'G-Y7KWHXBGXY',
      })
    ),
    provideAuth(() => getAuth()),
    provideAnalytics(() => getAnalytics()),
    ScreenTrackingService,
    UserTrackingService,
    provideFirestore(() => getFirestore()),
    provideFunctions(() => getFunctions()),
    provideMessaging(() => getMessaging()),
    provideStorage(() => getStorage()),
    provideAnimationsAsync(),
    provideAnimations(),
    provideHttpClient(),
    provideMarkdown({
      markedOptions: {
        provide: MARKED_OPTIONS,
        useFactory: markedOptionsFactory,
      },
    }),
  ],
};
