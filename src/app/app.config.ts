import { ApplicationConfig, isDevMode } from '@angular/core';
import {
  provideRouter,
  withComponentInputBinding,
  withInMemoryScrolling,
} from '@angular/router';

import { DOCUMENT } from '@angular/common';
import { provideHttpClient, withFetch } from '@angular/common/http';
import {
  getAnalytics,
  provideAnalytics,
  ScreenTrackingService,
  UserTrackingService,
} from '@angular/fire/analytics';
import { initializeApp, provideFirebaseApp } from '@angular/fire/app';
import { getAuth, GoogleAuthProvider, provideAuth } from '@angular/fire/auth';
import { getFirestore, provideFirestore } from '@angular/fire/firestore';
import { getFunctions, provideFunctions } from '@angular/fire/functions';
import { getMessaging, provideMessaging } from '@angular/fire/messaging';
import { getStorage, provideStorage } from '@angular/fire/storage';
import {
  provideClientHydration,
  withHttpTransferCacheOptions,
} from '@angular/platform-browser';
import { provideAnimations } from '@angular/platform-browser/animations';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideStore } from '@ngrx/store';
import { provideStoreDevtools } from '@ngrx/store-devtools';
import {
  MARKED_OPTIONS,
  MarkedOptions,
  MarkedRenderer,
  provideMarkdown,
} from 'ngx-markdown';
import { routes } from './app.routes';
import { WINDOW, windowProvider } from './providers/window';
import { appStateReducer } from './state/reducers';

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
    provideClientHydration(
      withHttpTransferCacheOptions({
        filter: req => !req.url.includes('/search/keywords'),
      })
    ),
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
        authDomain: 'lyrobin.com',
        messagingSenderId: '661598081211',
        measurementId: 'G-Y7KWHXBGXY',
      })
    ),
    provideAuth(() => getAuth()),
    {
      provide: GoogleAuthProvider,
      useFactory: () => {
        const provider = new GoogleAuthProvider();
        provider.setCustomParameters({
          prompt: 'select_account',
        });
        return provider;
      },
    },
    provideAnalytics(() => getAnalytics()),
    ScreenTrackingService,
    UserTrackingService,
    provideFirestore(() => getFirestore()),
    provideFunctions(() => getFunctions()),
    provideMessaging(() => getMessaging()),
    provideStorage(() => getStorage()),
    provideAnimationsAsync(),
    provideAnimations(),
    provideHttpClient(withFetch()),
    provideMarkdown({
      markedOptions: {
        provide: MARKED_OPTIONS,
        useFactory: markedOptionsFactory,
      },
    }),
    provideStore({ appState: appStateReducer }),
    provideStoreDevtools({ maxAge: 25, logOnly: !isDevMode(), trace: true }),
  ],
};
