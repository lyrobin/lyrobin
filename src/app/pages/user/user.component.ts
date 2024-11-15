import { Component, computed, effect, OnInit } from '@angular/core';
import { SearchBarComponent } from '../../components/search-bar/search-bar.component';
import { ActivatedRoute, Router } from '@angular/router';
import { AvatarModule } from 'primeng/avatar';
import { Store } from '@ngrx/store';
import { isUserLoggedIn, selectUser } from '../../state/selectors';
import { CardComponent } from '../../components/card/card.component';
import { CardModule } from 'primeng/card';
import { DividerModule } from 'primeng/divider';
import { InputTextModule } from 'primeng/inputtext';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { UserService } from '../../providers/user.service';

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

  geminiKey: string = '';
  updating: boolean = false;
  updateGeminiKeyIcon: string = '';
  clearIcon: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly store: Store,
    private router: Router,
    private route: ActivatedRoute,
    private userService: UserService
  ) {
    effect(() => {
      if (!this.isUserLoggedIn()) {
        this.router.navigate(['/']);
      }
    });
  }
  ngOnInit(): void {
    this.userService.getUserGeminiKey().then(key => {
      this.geminiKey = key;
    });
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
      .setUserGeminiKey(this.geminiKey)
      .then(() => {
        this.updateGeminiKeyIcon = 'pi pi-check';
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
