import { NgFor, NgIf, NgTemplateOutlet } from '@angular/common';
import {
  Component,
  ContentChild,
  ContentChildren,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
  TemplateRef,
} from '@angular/core';
import { CardModule } from 'primeng/card';
import { DataViewModule } from 'primeng/dataview';
import { PaginatorModule, PaginatorState } from 'primeng/paginator';
import { ScrollPanelModule } from 'primeng/scrollpanel';
import { Document, SearchResult } from '../../providers/search';
import { SkeletonModule } from 'primeng/skeleton';
import { MatIconModule } from '@angular/material/icon';
import { DoctypeIconPipe } from '../../utils/doctype-icon.pipe';
import { TooltipModule } from 'primeng/tooltip';
import { ProgressBarModule } from 'primeng/progressbar';
import { AicoreService } from '../../providers/aicore.service';
import { animate, style, transition, trigger } from '@angular/animations';
import { MarkdownModule } from 'ngx-markdown';
import { MarkdownSanitizePipe } from '../../utils/markdown-sanitize.pipe';
import {
  LayoutModule,
  BreakpointObserver,
  Breakpoints,
} from '@angular/cdk/layout';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { EventLoggerService } from '../../providers/event-logger.service';
import { SmartSummaryCardDirective } from '../../directives/smart-summary-card.directive';
import { LimitTextPipe } from '../../utils/limit-text.pipe';

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
  holdItem?: number;
  summary?: string;
  showSummary: boolean = false;
  loadingSummary: boolean = false;
  summaryTimeout?: ReturnType<typeof setTimeout>;
  isHandset: boolean = false;
  showDialog: boolean = false;

  constructor(
    private aicore: AicoreService,
    private breakpointObserver: BreakpointObserver,
    private logger: EventLoggerService
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
}
