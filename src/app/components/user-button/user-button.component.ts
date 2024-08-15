import { NgIf } from '@angular/common';
import { Component, computed, OnInit, ViewChild } from '@angular/core';
import {
  Auth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
} from '@angular/fire/auth';
import { Store } from '@ngrx/store';
import { signInWithRedirect } from 'firebase/auth';
import { MenuItem } from 'primeng/api';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { Menu, MenuModule } from 'primeng/menu';
import { OverlayPanelModule } from 'primeng/overlaypanel';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { environment } from '../../../environments/environment';
import {
  isLoadingAuth,
  isUserLoggedIn,
  selectUser,
} from '../../state/selectors';

@Component({
  selector: 'app-user-button',
  standalone: true,
  imports: [
    NgIf,
    ButtonModule,
    AvatarModule,
    OverlayPanelModule,
    MenuModule,
    ProgressSpinnerModule,
  ],
  templateUrl: './user-button.component.html',
  styleUrl: './user-button.component.scss',
})
export class UserButtonComponent implements OnInit {
  readonly isUserLoggedIn = this.store.selectSignal(isUserLoggedIn);
  readonly user = this.store.selectSignal(selectUser);
  readonly photo = computed(() => this.user()?.photoURL);
  readonly isLoading = this.store.selectSignal(isLoadingAuth);
  menuItems?: MenuItem[];

  @ViewChild('menu') menu!: Menu;

  constructor(
    private readonly store: Store,
    private auth: Auth,
    private googleAuth: GoogleAuthProvider
  ) {}

  ngOnInit(): void {
    this.menuItems = [
      {
        label: '登出',
        icon: 'pi pi-sign-out',
        command: () => this.logout(),
      },
    ];
  }

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

  logout() {
    signOut(this.auth);
  }

  openMenu(event: Event) {
    this.menu.toggle(event);
  }
}
