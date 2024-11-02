import { CommonModule } from '@angular/common';
import { Component, Input, OnInit, ViewChild } from '@angular/core';
import { Storage, getDownloadURL, ref } from '@angular/fire/storage';
import { ActivatedRoute, Router } from '@angular/router';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import { faCircleQuestion } from '@fortawesome/free-solid-svg-icons';
import { Store } from '@ngrx/store';
import { MarkdownComponent } from 'ngx-markdown';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DialogModule } from 'primeng/dialog';
import { DividerModule } from 'primeng/divider';
import { TagModule } from 'primeng/tag';
import { NewsReport } from '../../providers/document';
import { isUserLoggedIn } from '../../state/selectors';
import { LimitTextPipe } from '../../utils/limit-text.pipe';
import { LoginDialogComponent } from '../login-dialog/login-dialog.component';
@Component({
  selector: 'app-news-report',
  standalone: true,
  imports: [
    CardModule,
    MarkdownComponent,
    CommonModule,
    TagModule,
    LimitTextPipe,
    ButtonModule,
    FontAwesomeModule,
    LoginDialogComponent,
    DialogModule,
    MarkdownComponent,
    DividerModule,
  ],
  templateUrl: './news-report.component.html',
  styleUrl: './news-report.component.scss',
})
export class NewsReportComponent implements OnInit {
  @Input({ required: true }) newsReport!: NewsReport;
  @ViewChild('loginDialog') loginDialog!: LoginDialogComponent;

  readonly hintIcon = faCircleQuestion;
  readonly fullTextDownloadHint = `
  ### 全文下載是什麼?
  全文下載是一個功能，讓您可以下載生成這一則新聞的原始資料，包括本週的會議記錄、立法院議事錄、立委質詢等等。
  
  ### 全文檔案可以做什麼?
  您可以透過上傳全文檔案到您喜歡的 AI 模型，例如 ChatGPT、Gemini 等等，讓您可以針對這則新聞進行更深入的分析。
  `;

  isUserLoggedIn$ = this.store.selectSignal(isUserLoggedIn);
  isExpanded: boolean = false;
  fullTextDialogMessage: string = `
  全文下載是一個功能，讓您可以下載生成這一則新聞的原始資料，包括本週的會議記錄、立法院議事錄、立委質詢等等。
  
  ### 全文檔案可以做什麼?
  您可以透過上傳全文檔案到您喜歡的 AI 模型，例如 ChatGPT、Gemini 等等，讓您可以針對這則新聞進行更深入的分析。
  `;
  fullTextDialogVisible: boolean = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private store: Store,
    private storage: Storage
  ) {}

  ngOnInit(): void {
    if (this.newsReport.content.length < 120) {
      this.isExpanded = true;
    }
  }

  private getDateRange(): string {
    const now = new Date(this.newsReport.report_date);
    const dayOfWeek = now.getDay();
    const start = new Date(now);
    const end = new Date(now);
    const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    start.setDate(now.getDate() + diffToMonday);
    start.setHours(0, 0, 0, 0); // Set to start of the day
    const diffToSunday = dayOfWeek === 0 ? 0 : 7 - dayOfWeek;
    end.setDate(now.getDate() + diffToSunday);
    end.setHours(23, 59, 59, 999); // Set to end of the day
    const startDate = `${start.getFullYear()}年${start.getMonth() + 1}月${start.getDate()}日`;
    const endDate = `${end.getFullYear()}年${end.getMonth() + 1}月${end.getDate()}日`;
    return `${startDate} - ${endDate}`;
  }

  searchKeyword(tag: string) {
    this.router.navigate(['search'], {
      relativeTo: this.route,
      queryParams: {
        query: tag,
        page: 1,
        filter: `created_date=${this.getDateRange()}`,
      },
    });
  }

  searchLegislator(legislator: string) {
    this.router.navigate(['search'], {
      relativeTo: this.route,
      queryParams: {
        query: '*',
        page: 1,
        filter: `legislator=${legislator},created_date=${this.getDateRange()}`,
      },
    });
  }

  onDownloadFullTextButtonClick() {
    if (!this.isUserLoggedIn$()) {
      this.loginDialog.toggle();
      this.loginDialog.message = this.fullTextDownloadHint;
    } else {
      this.fullTextDialogVisible = true;
    }
  }

  downloadFullText() {
    this.fullTextDialogVisible = false;
    getDownloadURL(ref(this.storage, this.newsReport.source_uri)).then(url => {
      const link = document.createElement('a');
      link.href = url;
      link.download =
        'report_' +
        (this.newsReport.source_uri.split('/').pop() ?? 'full_text.md');
      link.target = '_blank';
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    });
  }
}
