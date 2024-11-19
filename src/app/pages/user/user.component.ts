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
import { DialogModule } from 'primeng/dialog';
import { MarkdownModule } from 'ngx-markdown';

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
    DialogModule,
    MarkdownModule,
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
  showKeyDialog: boolean = false;
  keyMessage: string = `
  ## 如何如得 Gemini 金鑰？

  你可以在 Google AI Studio 取得 Gemini 金鑰，來啟用 AI 功能。可以參考以下步驟：

  1. 打開左側選單，點選「Get API Key」。
  2. 在中間主畫面點選「Create API Key」。
  3. 點選「Copy」按鈕，將金鑰複製到剪貼簿。
  4. 若是先前已經取得過金鑰，選擇任一個 Google Cloud Project，再點選「Create API key in existing project」。 
  
  你也可以查看 <a href="http://www.youtube.com/" target="_blank">影片教學</a>，來了解如何取得 Gemini 金鑰。
  `;

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

  toggleKeyDialog() {
    this.showKeyDialog = !this.showKeyDialog;
  }

  gotoAiStudio() {
    window.open('https://aistudio.google.com/apikey', '_blank');
  }
}
