import { Component, computed, effect, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Store } from '@ngrx/store';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DividerModule } from 'primeng/divider';
import { InputTextModule } from 'primeng/inputtext';
import { SearchBarComponent } from '../../components/search-bar/search-bar.component';
import { AicoreService } from '../../providers/aicore.service';
import { UserService } from '../../providers/user.service';
import { AppStateActions } from '../../state/actions';
import {
  isUserLoggedIn,
  selectGeminiKey,
  selectUser,
} from '../../state/selectors';

@Component({
  selector: 'app-user',
  standalone: true,
  imports: [
    SearchBarComponent,
    AvatarModule,
    CardModule,
    DividerModule,
    InputTextModule,
    FormsModule,
    ButtonModule,
  ],
  templateUrl: './user.component.html',
  styleUrl: './user.component.scss',
})
export class UserComponent implements OnInit {
  readonly user = this.store.selectSignal(selectUser);
  readonly isUserLoggedIn = this.store.selectSignal(isUserLoggedIn);
  readonly photo = computed(() => this.user()?.photoURL);
  readonly geminiKey = this.store.selectSignal(selectGeminiKey);

  key: string = '';
  updating: boolean = false;
  updateGeminiKeyIcon: string = '';
  clearIcon: ReturnType<typeof setTimeout> | null = null;
  buffer: string = '';

  constructor(
    private readonly store: Store,
    private router: Router,
    private route: ActivatedRoute,
    private userService: UserService,
    private aicore: AicoreService
  ) {
    effect(() => {
      if (!this.isUserLoggedIn()) {
        this.router.navigate(['/']);
      }
    });
  }
  ngOnInit(): void {
    this.key = this.geminiKey() || '';
  }

  onSearch(query: string) {
    this.router.navigate(['search'], {
      relativeTo: this.route,
      queryParams: { query, page: 1 },
    });
  }

  updateGeminiKey() {
    if (this.clearIcon) {
      clearTimeout(this.clearIcon);
    }
    this.updating = true;
    this.userService
      .setUserGeminiKey(this.key)
      .then(() => {
        this.updateGeminiKeyIcon = 'pi pi-check';
        this.store.dispatch(
          AppStateActions.setGeminiKey({ geminiKey: this.key })
        );
      })
      .catch(() => {
        this.updateGeminiKeyIcon = 'pi pi-times';
      })
      .finally(() => {
        this.updating = false;
        this.clearIcon = setTimeout(() => {
          this.updateGeminiKeyIcon = '';
        }, 1000);
      });
  }
}
