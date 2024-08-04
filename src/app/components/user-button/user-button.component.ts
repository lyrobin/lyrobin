import { NgIf } from '@angular/common';
import { Component, computed, OnInit, ViewChild } from '@angular/core';
import {
  Auth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
} from '@angular/fire/auth';
import { Store } from '@ngrx/store';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { OverlayPanel, OverlayPanelModule } from 'primeng/overlaypanel';
import { isUserLoggedIn, selectUser } from '../../state/selectors';
import { Menu, MenuModule } from 'primeng/menu';
import { MenuItem } from 'primeng/api';

@Component({
  selector: 'app-user-button',
  standalone: true,
  imports: [NgIf, ButtonModule, AvatarModule, OverlayPanelModule, MenuModule],
  templateUrl: './user-button.component.html',
  styleUrl: './user-button.component.scss',
})
export class UserButtonComponent implements OnInit {
  readonly isUserLoggedIn = this.store.selectSignal(isUserLoggedIn);
  readonly user = this.store.selectSignal(selectUser);
  readonly photo = computed(() => this.user()?.photoURL);
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
    signInWithPopup(this.auth, this.googleAuth)
      .then(result => {
        const cred = GoogleAuthProvider.credentialFromResult(result);
        console.log(cred);
      })
      .catch(error => {
        console.log(error);
      })
      .finally(() => {
        console.log(this.isUserLoggedIn());
        console.log(this.user());
      });
  }

  logout() {
    signOut(this.auth);
  }

  openMenu(event: Event) {
    this.menu.toggle(event);
  }
}
