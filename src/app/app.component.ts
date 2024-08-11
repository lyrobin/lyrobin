import { DOCUMENT, isPlatformBrowser } from '@angular/common';
import { Component, Inject, inject, OnInit, PLATFORM_ID } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Analytics } from '@angular/fire/analytics';
import { Auth, connectAuthEmulator } from '@angular/fire/auth';
import { connectFirestoreEmulator, Firestore } from '@angular/fire/firestore';
import { connectStorageEmulator, Storage } from '@angular/fire/storage';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterOutlet,
} from '@angular/router';
import { config, dom } from '@fortawesome/fontawesome-svg-core';
import { Store } from '@ngrx/store';
import { getRedirectResult, onAuthStateChanged } from 'firebase/auth';
import { filter, map, startWith } from 'rxjs';
import { environment } from '../environments/environment';
import { AngularIconComponent } from './components/icons/angular-icon.component';
import { ArrowBackIconComponent } from './components/icons/arrow-back-icon.component';
import { FirebaseIconComponent } from './components/icons/firebase-icon.component';
import { AppStateActions } from './state/actions';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterOutlet,
    AngularIconComponent,
    FirebaseIconComponent,
    ArrowBackIconComponent,
    RouterLink,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  private readonly router = inject(Router);
  private readonly analytics = environment.production
    ? inject(Analytics)
    : null;
  private readonly store = inject(Store);
  private readonly auth = inject(Auth);
  private readonly storage = inject(Storage);
  private readonly db = inject(Firestore);
  private readonly isMainPage$ = this.router.events.pipe(
    filter((event): event is NavigationEnd => event instanceof NavigationEnd),
    map((event: NavigationEnd) => event.url === '/'),
    startWith(true)
  );
  private isBrowser: boolean;

  isMainPage = toSignal(this.isMainPage$);

  constructor(
    @Inject(DOCUMENT) private document: Document,
    @Inject(PLATFORM_ID) platformId: any
  ) {
    config.autoAddCss = false;
    let head = this.document.getElementsByTagName('head')[0];
    let styleNode = this.document.createElement('style');
    styleNode.innerHTML = dom.css(); // grab FA's CSS
    head.appendChild(styleNode);
    this.isBrowser = isPlatformBrowser(platformId);
  }
  ngOnInit(): void {
    if (!environment.production) {
      connectAuthEmulator(this.auth, 'http://127.0.0.1:9099', {
        disableWarnings: true,
      });
      connectStorageEmulator(this.storage, '127.0.0.1', 9199);
      connectFirestoreEmulator(this.db, '127.0.0.1', 8080);
    }
    if (this.isBrowser) {
      console.log('check redirect');
      getRedirectResult(this.auth)
        .then(result => console.log(result))
        .catch(err => console.log(err))
        .finally(() => console.log('redirect done'));
    }

    onAuthStateChanged(this.auth, user => {
      if (user) {
        this.store.dispatch(
          AppStateActions.loginUser({
            user: {
              uid: user.uid,
              displayName: user.displayName || undefined,
              photoURL: user.photoURL || undefined,
            },
          })
        );
      } else {
        this.store.dispatch(AppStateActions.logoutUser({}));
      }
    });
  }
}
