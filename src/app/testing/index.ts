import { provideFirebaseApp } from '@angular/fire/app';
import {
  connectAuthEmulator,
  getAuth,
  GoogleAuthProvider,
  provideAuth,
} from '@angular/fire/auth';
import {
  connectFirestoreEmulator,
  getFirestore,
  provideFirestore,
} from '@angular/fire/firestore';
import { getStorage, provideStorage } from '@angular/fire/storage';
import {
  provideRouter,
  withComponentInputBinding,
  withInMemoryScrolling,
} from '@angular/router';
import { initializeApp } from 'firebase/app';
import { connectStorageEmulator } from 'firebase/storage';
import { routes } from '../app.routes';

export const providersForTest = [
  provideFirebaseApp(() =>
    initializeApp({
      projectId: 'taiwan-legislative-search',
      appId: '1:661598081211:web:febbd559cbf3295bdb999e',
      storageBucket: 'taiwan-legislative-search.appspot.com',
      apiKey: 'AIzaSyCWElTvWiGH7rZMxFl2s5xEbsLXDo3Ub44',
      authDomain: 'app.lyrobin.com',
      messagingSenderId: '661598081211',
      measurementId: 'G-Y7KWHXBGXY',
    })
  ),
  provideStorage(() => {
    const storage = getStorage();
    connectStorageEmulator(storage, '127.0.0.1', 9199);
    return storage;
  }),
  provideAuth(() => {
    const auth = getAuth();
    connectAuthEmulator(auth, 'http://127.0.0.1:9099', {
      disableWarnings: true,
    });
    return auth;
  }),
  provideFirestore(() => {
    const db = getFirestore();
    connectFirestoreEmulator(db, '127.0.0.1', 8080);
    return db;
  }),
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
  provideRouter(
    routes,
    withComponentInputBinding(),
    withInMemoryScrolling({
      scrollPositionRestoration: 'enabled',
    })
  ),
];
