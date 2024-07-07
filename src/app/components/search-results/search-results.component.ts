import { NgFor, NgIf } from '@angular/common';
import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
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
  holdInterval?: ReturnType<typeof setInterval>;
  holdMilliseconds: number = 0;
  holdItem?: number;
  summary?: string;
  showSummary: boolean = false;
  loadingSummary: boolean = false;
  summaryTimeout?: ReturnType<typeof setTimeout>;
  readonly holdTotalMilliseconds = 2500;
  readonly holdIntervalStep = 300;
  isHandset: boolean = false;
  showDialog: boolean = false;

  constructor(
    private aicore: AicoreService,
    private breakpointObserver: BreakpointObserver
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

  get holdProgress(): number {
    let progress = Math.round(
      Math.min(this.holdMilliseconds / this.holdTotalMilliseconds, 1) * 100
    );
    if (progress > 60) {
      return 100;
    }
    return progress;
  }

  onPage(event: PaginatorState) {
    this.onPageChange.emit(
      Math.floor((event.first ?? 0) / (event.rows ?? 1)) + 1
    );
  }

  onHoldDescription(event: MouseEvent | TouchEvent, hit: Hit, index: number) {
    if (this.holdInterval) {
      clearInterval(this.holdInterval);
      this.holdItem = undefined;
    }
    this.holdMilliseconds = 0;
    this.holdItem = index;
    this.holdInterval = setInterval(() => {
      this.holdMilliseconds += this.holdIntervalStep;
      if (this.holdMilliseconds >= this.holdTotalMilliseconds) {
        clearInterval(this.holdInterval);
        this.holdInterval = undefined;
        this.holdMilliseconds = 0;
        this.holdItem = undefined;
        this.aiSummary(hit);
      }
    }, this.holdIntervalStep);
  }

  aiSummary(doc: Document) {
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

  onLeaveDescription(event: MouseEvent | TouchEvent, hit: Hit, index: number) {
    console.log('leave');
    if (this.holdInterval) {
      clearInterval(this.holdInterval);
      this.holdInterval = undefined;
    }
    this.holdItem = undefined;
    this.holdMilliseconds = 0;
  }
}
