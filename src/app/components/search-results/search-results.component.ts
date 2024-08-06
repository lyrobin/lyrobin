import { animate, style, transition, trigger } from '@angular/animations';
import {
  BreakpointObserver,
  Breakpoints,
  LayoutModule,
} from '@angular/cdk/layout';
import { NgFor, NgIf, NgTemplateOutlet } from '@angular/common';
import {
  Component,
  ContentChild,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
  TemplateRef,
  ViewChild,
} from '@angular/core';
import { Storage, getBlob, ref } from '@angular/fire/storage';
import { MatIconModule } from '@angular/material/icon';
import { Store } from '@ngrx/store';
import { MarkdownModule } from 'ngx-markdown';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DataViewModule } from 'primeng/dataview';
import { DialogModule } from 'primeng/dialog';
import { PaginatorModule, PaginatorState } from 'primeng/paginator';
import { ProgressBarModule } from 'primeng/progressbar';
import { ScrollPanelModule } from 'primeng/scrollpanel';
import { SkeletonModule } from 'primeng/skeleton';
import { TooltipModule } from 'primeng/tooltip';
import { SmartSummaryCardDirective } from '../../directives/smart-summary-card.directive';
import { AicoreService } from '../../providers/aicore.service';
import { DocumentService } from '../../providers/document.service';
import { EventLoggerService } from '../../providers/event-logger.service';
import { Document, SearchResult } from '../../providers/search';
import { isUserLoggedIn } from '../../state/selectors';
import { DoctypeIconPipe } from '../../utils/doctype-icon.pipe';
import { LimitTextPipe } from '../../utils/limit-text.pipe';
import { MarkdownSanitizePipe } from '../../utils/markdown-sanitize.pipe';
import { LoginDialogComponent } from '../login-dialog/login-dialog.component';

interface Hit extends Document {
  focus: boolean;
}

@Component({
  selector: 'app-search-results',
  standalone: true,
  imports: [
    CardModule,
    DataViewModule,
    NgFor,
    NgIf,
    PaginatorModule,
    ScrollPanelModule,
    SkeletonModule,
    MatIconModule,
    DoctypeIconPipe,
    TooltipModule,
    ProgressBarModule,
    MarkdownModule,
    MarkdownSanitizePipe,
    LayoutModule,
    DialogModule,
    ButtonModule,
    NgTemplateOutlet,
    LimitTextPipe,
    LoginDialogComponent,
  ],
  templateUrl: './search-results.component.html',
  styleUrl: './search-results.component.scss',
  animations: [
    trigger('inoutTrigger', [
      transition(':enter', [
        style({ opacity: 0 }),
        animate('500ms', style({ opacity: 1 })),
      ]),
      transition(':leave', [animate('500ms', style({ opacity: 0 }))]),
    ]),
    trigger('inTrigger', [
      transition(':enter', [
        style({ opacity: 0 }),
        animate('500ms', style({ opacity: 1 })),
      ]),
    ]),
  ],
})
export class SearchResultsComponent implements OnChanges {
  @Input() result?: SearchResult;
  @Input() rows: number = 20;
  @Input() page: number = 1;
  @Input() loading: boolean = false;
  @Output() onPageChange = new EventEmitter<number>();
  @ContentChild(SmartSummaryCardDirective, { read: TemplateRef })
  smartSummaryCardTemplate?: any;
  @ViewChild('loginDialog') loginDialog!: LoginDialogComponent;
  holdItem?: number;
  summary?: string;
  showSummary: boolean = false;
  loadingSummary: boolean = false;
  summaryTimeout?: ReturnType<typeof setTimeout>;
  isHandset: boolean = false;
  showDialog: boolean = false;
  isUserLoggedIn$ = this.store.selectSignal(isUserLoggedIn);
  loginDialogMessage: string = '';

  constructor(
    private aicore: AicoreService,
    private breakpointObserver: BreakpointObserver,
    private logger: EventLoggerService,
    private store: Store,
    private storage: Storage,
    private documents: DocumentService
  ) {
    this.breakpointObserver.observe([Breakpoints.Handset]).subscribe(result => {
      this.isHandset = result.matches;
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    let loading = changes['loading'];
    if (loading?.previousValue !== loading?.currentValue) {
      this.summary = undefined;
      this.showSummary = false;
    }
  }

  get totalRecords(): number {
    return this.result?.found || 0;
  }

  get first(): number {
    return Math.max((this.page - 1) * this.rows, 0);
  }

  get hits(): Hit[] {
    return (
      this.result?.hits?.map((d, i) => ({
        ...d,
        focus: i === this.holdItem,
      })) || []
    );
  }

  onPage(event: PaginatorState) {
    this.onPageChange.emit(
      Math.floor((event.first ?? 0) / (event.rows ?? 1)) + 1
    );
  }

  dbClickDescription(doc: Document) {
    this.logger.logClickDescription(doc.doctype);
  }

  aiSummary(doc: Document) {
    this.logger.logAiSummarize(doc.doctype);
    this.showSummary = true;
    if (this.isHandset) {
      this.showDialog = true;
    }
    this.loadingSummary = true;
    if (this.summaryTimeout) {
      clearTimeout(this.summaryTimeout);
    }
    this.aicore.summary(doc).then(summary => {
      this.summary = summary;
      this.summaryTimeout = setTimeout(() => {
        this.loadingSummary = false;
        if (!this.summary) {
          this.summaryTimeout = setTimeout(() => {
            this.showSummary = false;
          }, 5000);
        }
      }, 1500);
    });
  }

  downloadVideo(d: Document) {
    if (!this.isUserLoggedIn$()) {
      this.loginDialogMessage = '只需登入即可下載，您的參與是我們最大的動力！';
      this.loginDialog.toggle();
      return;
    }
    this.documents
      .getSpeechVideo(d.path)
      .then(url => getBlob(ref(this.storage, url)))
      .then(blob => {
        const url = URL.createObjectURL(blob);
        console.log(url);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'video.mp4';
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      })
      .catch(err => {
        console.error(err);
      });
  }
}
