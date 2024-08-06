import { Component, Input } from '@angular/core';
import { Auth, GoogleAuthProvider, signInWithPopup } from '@angular/fire/auth';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { DividerModule } from 'primeng/divider';

@Component({
  selector: 'app-login-dialog',
  standalone: true,
  imports: [DialogModule, DividerModule, ButtonModule],
  templateUrl: './login-dialog.component.html',
  styleUrl: './login-dialog.component.scss',
})
export class LoginDialogComponent {
  visible: boolean = false;
  @Input() message: string = '請先登入';

  constructor(
    private auth: Auth,
    private googleAuth: GoogleAuthProvider
  ) {}

  toggle() {
    this.visible = !this.visible;
  }

  login() {
    signInWithPopup(this.auth, this.googleAuth).finally(() => {
      this.visible = false;
    });
  }
}
