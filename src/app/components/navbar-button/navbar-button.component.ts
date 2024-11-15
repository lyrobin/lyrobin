import { Component, computed } from '@angular/core';
import {
  Auth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
} from '@angular/fire/auth';
import { ActivatedRoute, Router } from '@angular/router';
import { Store } from '@ngrx/store';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { MenuModule } from 'primeng/menu';
import { SidebarModule } from 'primeng/sidebar';
import { environment } from '../../../environments/environment';
import { isUserLoggedIn, selectUser } from '../../state/selectors';
import { FaIconComponent } from '@fortawesome/angular-fontawesome';
import { faGear } from '@fortawesome/free-solid-svg-icons';

@Component({
  selector: 'app-navbar-button',
  standalone: true,
  imports: [
    ButtonModule,
    SidebarModule,
    MenuModule,
    AvatarModule,
    FaIconComponent,
  ],
  templateUrl: './navbar-button.component.html',
  styleUrl: './navbar-button.component.scss',
})
export class NavbarButtonComponent {
  readonly isUserLoggedIn = this.store.selectSignal(isUserLoggedIn);
  readonly user = this.store.selectSignal(selectUser);
  readonly userPhoto = computed(() => this.user()?.photoURL);
  readonly userName = computed(() => this.user()?.displayName);
  readonly gearIcon = faGear;
  navbarVisible = false;

  constructor(
    private store: Store,
    private auth: Auth,
    private googleAuth: GoogleAuthProvider,
    private router: Router,
    private route: ActivatedRoute
  ) {}

  get userLabel(): string {
    return this.user()?.displayName?.at(0) ?? '';
  }

  login() {
    if (environment.production) {
      signInWithRedirect(this.auth, this.googleAuth);
    } else {
      signInWithPopup(this.auth, this.googleAuth);
    }
  }

  gotoNews() {
    this.router.navigate(['/news'], {
      relativeTo: this.route,
    });
  }

  gotoPrivacy() {
    this.router.navigate(['/privacy'], {
      relativeTo: this.route,
    });
  }

  gotoChat() {
    this.router.navigate(['/chat'], {
      relativeTo: this.route,
    });
  }
}
