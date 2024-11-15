import { Component, effect, ElementRef, ViewChild } from '@angular/core';
import { SearchBarComponent } from '../../components/search-bar/search-bar.component';
import { ActivatedRoute, Router } from '@angular/router';
import { Store } from '@ngrx/store';
import {
  isUserLoggedIn,
  selectChatContext,
  selectGeminiKey,
  isLoadingAuth,
  selectChatHistory,
  selectUser,
} from '../../state/selectors';
import { SearchService } from '../../providers/search.service';
import { AppStateActions } from '../../state/actions';
import { CardModule } from 'primeng/card';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { MarkdownModule } from 'ngx-markdown';
import { ButtonModule } from 'primeng/button';
import { ScrollPanelModule } from 'primeng/scrollpanel';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { FormsModule } from '@angular/forms';
import { AicoreService } from '../../providers/aicore.service';
import { AvatarModule } from 'primeng/avatar';
import { TagModule } from 'primeng/tag';
import { DividerModule } from 'primeng/divider';

interface Message {
  message: string;
  role: string;
  loading?: boolean;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [
    SearchBarComponent,
    CardModule,
    ProgressSpinnerModule,
    MarkdownModule,
    ButtonModule,
    ScrollPanelModule,
    IconFieldModule,
    InputIconModule,
    InputTextModule,
    FormsModule,
    AvatarModule,
    TagModule,
    DividerModule,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
  host: { ngSkipHydration: 'true' },
})
export class ChatComponent {
  readonly chatContext = this.store.selectSignal(selectChatContext);
  readonly isLogin = this.store.selectSignal(isUserLoggedIn);
  readonly isUserLoading = this.store.selectSignal(isLoadingAuth);
  readonly geminiKey = this.store.selectSignal(selectGeminiKey);
  readonly contextHistory = this.store.selectSignal(selectChatHistory);
  readonly user = this.store.selectSignal(selectUser);

  @ViewChild('chatscroll') chatScroll!: ElementRef;

  readonly errorNeedLogin = `
  立即登入以使用 Gemini 來深度分析目前搜尋到的資料，快加入我們來探索立院大小事！
  `;

  readonly errorNeedGeminiKey = `
  我們需要您的 Gemini 金鑰來進行分析，請至個人設定頁面設定您的金鑰。
  `;

  readonly errorNoData = `
  目前沒有足夠的前後文可以供 Gemini 進行分析，請嘗試搜尋其他關鍵字。

  **提示：**
  
  您可以透過上方的搜尋欄位來搜尋您感興趣的關鍵字。
  
  也可以回到首頁來瀏覽其他內容，再點擊搜尋列右方 Gemini 圖示來進行分析。 ![](/assets/gemini-icon.png)
  `;

  loading: boolean = true;
  query: string = '';
  filter: string = '';
  originalFilter: string = '';
  filterParams: { [name: string]: string } = {};
  history: Message[] = [];
  message: string | undefined;
  reloadTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private store: Store,
    private search: SearchService,
    private aicore: AicoreService
  ) {
    this.route.queryParams.subscribe(params => {
      this.originalFilter = params['filter'] ?? '';
      this.filterParams = ((params['filter'] as string) ?? '')
        .split(',')
        .reduce(
          (acc, f) => {
            const [key, value] = f.split('=');
            acc[key] = value;
            return acc;
          },
          {} as { [name: string]: string }
        );
      this.query = params['query'] ?? '';
      this.filter = this.search.toFilterString(this.filterParams);
      if (this.reloadTimer) {
        clearTimeout(this.reloadTimer);
      }
      this.reloadTimer = setTimeout(() => {
        this.reload();
      }, 500);
    });
    effect(() => {
      if (this.isLogin()) {
        if (this.reloadTimer) {
          clearTimeout(this.reloadTimer);
        }
        this.reloadTimer = setTimeout(() => {
          this.reload();
        }, 500);
      }
    });
  }

  get hasContext(): boolean {
    return this.chatContext()?.content !== '';
  }

  get tags(): string[] {
    return Object.values(this.filterParams).filter(
      v => v !== '' && v !== undefined
    );
  }

  get words(): string {
    return `${this.chatContext()?.content.length} 字`;
  }

  get errorTitle(): string {
    if (this.isUserLoading() || this.loading) {
      return '';
    }
    if (!this.isLogin()) {
      return '我們需要你的加入！';
    }
    if (!this.geminiKey()) {
      return '需要 Gemini 金鑰';
    }
    if (!this.chatContext()?.content) {
      return '目前沒有資料可以使用';
    }
    return '';
  }

  get errorMessage(): string {
    if (this.isUserLoading() || this.loading) {
      return '';
    }
    if (!this.isLogin()) {
      return this.errorNeedLogin;
    }
    if (!this.geminiKey()) {
      return this.errorNeedGeminiKey;
    }
    if (!this.chatContext()?.content) {
      return this.errorNoData;
    }
    return '';
  }

  reload() {
    this.loading = true;
    const changed =
      this.chatContext()?.query !== this.query ||
      this.chatContext()?.filter !== this.filter;
    if (!changed && this.chatContext()?.loaded) {
      this.loading = false;
      this.history.splice(
        0,
        this.history.length ?? 0,
        ...(this.contextHistory()
          ?.slice(1)
          .map(m => {
            return { message: m.message, role: m.role, loading: false };
          }) ?? [])
      );
      return;
    }

    this.store.dispatch(
      AppStateActions.setChatContext({
        context: {
          query: this.query,
          filter: this.filter,
          content: '',
          loaded: false,
        },
      })
    );
    console.log('fetching context');
    this.search
      .fetchContext(this.query, this.filter)
      .then(content => {
        this.store.dispatch(
          AppStateActions.setChatContext({
            context: {
              query: this.query,
              filter: this.filter,
              content: content,
              loaded: true,
            },
          })
        );
        this.store.dispatch(
          AppStateActions.clearChatHistory({
            _: undefined,
          })
        );
        this.store.dispatch(
          AppStateActions.addChatHistory({
            message: { message: content, role: 'user' },
          })
        );
      })
      .catch(e => {
        console.error(e);
      })
      .finally(() => {
        this.loading = false;
      });
  }

  onSearch(query: string) {
    this.router.navigate(['.'], {
      relativeTo: this.route,
      onSameUrlNavigation: 'reload',
      queryParams: { query: query },
    });
  }

  gotoUser() {
    this.router.navigate(['user']);
  }

  sendMessage() {
    if (!this.message) {
      return;
    }
    this.history.push({
      message: this.message,
      role: 'user',
      loading: false,
    });
    this.history.push({
      message: '',
      role: 'model',
      loading: true,
    });
    const userMessage = this.message ?? '';
    this.message = '';
    this.aicore
      .chat(userMessage ?? '')
      .then(reply => {
        reply.subscribe({
          next: r => {
            this.history[this.history.length - 1].message += r.text();
            console.log(r.text());
            this.chatScroll.nativeElement.scrollTop =
              this.chatScroll.nativeElement.scrollHeight;
          },
          complete: () => {
            this.history[this.history.length - 1].loading = false;
            this.store.dispatch(
              AppStateActions.addChatHistory({
                message: {
                  message: userMessage,
                  role: 'user',
                },
              })
            );
            this.store.dispatch(
              AppStateActions.addChatHistory({
                message: this.history[this.history.length - 1],
              })
            );
            this.message = '';
            this.chatScroll.nativeElement.scrollTop =
              this.chatScroll.nativeElement.scrollHeight;
          },
        });
      })
      .catch(e => {
        this.history[this.history.length - 1].loading = false;
        this.history[this.history.length - 1].message =
          'Oops! 出了點問題，請稍後再試。';
        console.error(e);
      });
  }

  gotoSearch() {
    this.router.navigate(['/search'], {
      relativeTo: this.route,
      queryParams: {
        query: this.query,
        filter: this.originalFilter,
      },
    });
  }
}
