import { Component, Input, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  FacetChange,
  SearchBarComponent,
} from '../../components/search-bar/search-bar.component';
import { SearchResultsComponent } from '../../components/search-results/search-results.component';
import { SmartCardComponent } from '../../components/smart-card/smart-card.component';
import { SmartSummaryCardDirective } from '../../directives/smart-summary-card.directive';
import { EventLoggerService } from '../../providers/event-logger.service';
import {
  Facet,
  LegislatorRemark,
  SearchResult,
  Topic,
} from '../../providers/search';
import { SearchService } from '../../providers/search.service';
import { translate } from '../../utils/facet-value.pipe';
import { LoginDialogComponent } from '../../components/login-dialog/login-dialog.component';
import { Store } from '@ngrx/store';
import { isUserLoggedIn } from '../../state/selectors';

@Component({
  selector: 'app-search-view',
  standalone: true,
  imports: [
    SearchBarComponent,
    SearchResultsComponent,
    SmartCardComponent,
    SmartSummaryCardDirective,
    LoginDialogComponent,
  ],
  templateUrl: './search-view.component.html',
  styleUrl: './search-view.component.scss',
})
export class SearchViewComponent {
  @Input() query?: string;
  @Input() page?: number;
  @Input() filter?: string;
  @ViewChild('loginDialog') loginDialog!: LoginDialogComponent;
  result?: SearchResult;
  loading: boolean = true;
  legislatorRemark?: LegislatorRemark;
  aiTopic?: Topic;
  isUserLoggedIn = this.store.selectSignal(isUserLoggedIn);
  loginDialogMessage: string =
    '透過 Gemini 來深度分析目前搜尋到的資料，快加入我們來探索立院大小事！';

  constructor(
    private searchService: SearchService,
    private router: Router,
    private route: ActivatedRoute,
    private logger: EventLoggerService,
    private store: Store
  ) {
    this.route.queryParams.subscribe(params => {
      this.query = params['query'];
      this.page = params['page'];
      this.filter = params['filter'];
      this.reload();
    });
  }

  reload() {
    this.loading = true;
    this.searchService
      .search(this.query ?? '', this.filters, this.currentPage)
      .then(result => {
        this.result = result;
      })
      .finally(() => {
        this.logger.logSearch(this.query ?? '');
        this.loading = false;
      });
    this.loadLegislator();
    this.loadTopic();
  }

  private loadLegislator() {
    this.legislatorRemark = undefined;
    if (!this.query || this.query.length < 2) {
      return;
    } else if ((this.page || 0) > 1) {
      return;
    } else if (this.filter) {
      return;
    }
    this.searchService.legislator(this.query).then(result => {
      if (result) {
        this.legislatorRemark = result;
      }
    });
  }

  private loadTopic() {
    this.aiTopic = undefined;
    let tags = this.query
      ?.split(' ')
      .filter(t => t.startsWith('#'))
      .map(t => t.slice(1));
    if (tags?.length) {
      this.searchService.topic(tags).then(topic => {
        if (topic && (topic.summary?.length ?? 0) > 0) {
          this.aiTopic = topic;
        }
      });
    }
    let queries = this.query?.split(' ');
    if (queries?.length == 1) {
      queries = [queries[0]];
      this.searchService.topic(queries).then(topic => {
        if (topic && (topic.summary?.length ?? 0) > 0) {
          this.aiTopic = topic;
        }
      });
    }
  }

  get showSmartCard(): boolean {
    if (this.loading) {
      return false;
    }
    if (this.legislatorRemark) {
      return true;
    }
    if (this.aiTopic) {
      return true;
    }
    return false;
  }

  get currentPage(): number {
    return (this.page || 0) <= 0 ? 1 : this.page!;
  }

  get filters(): { [name: string]: string } {
    if (!this.filter) {
      return {};
    }
    let results: { [name: string]: string } = {};
    for (let f of this.filter.split(',')) {
      let [facet, value] = f.split('=');
      results[facet] = value;
    }
    return results;
  }

  get filterArray(): FacetChange[] {
    return Object.entries(this.filters).map(([facet, value]) => {
      return { facet, value: translate(value) };
    });
  }

  get facets(): Facet[] {
    let results: Facet[] = [];
    for (let facet of this.result?.facet ?? []) {
      if (!(facet.field in this.filters)) {
        results.push(facet);
      }
    }
    return results;
  }

  onPageChange(page: number) {
    this.router.navigate(['.'], {
      relativeTo: this.route,
      onSameUrlNavigation: 'reload',
      queryParams: {
        query: this.query,
        page: page,
        filter: this.stringifyFilters(this.filters),
      },
    });
  }

  onSearch(query: string) {
    this.router.navigate(['.'], {
      relativeTo: this.route,
      onSameUrlNavigation: 'reload',
      queryParams: { query: query, page: 1 },
    });
  }

  onFacetChange(event: FacetChange) {
    let newFilters = { ...this.filters, [event.facet]: event.value };
    newFilters = Object.entries(newFilters).reduce(
      (d, [k, v]) => {
        if (v) {
          d[k] = v;
        }
        return d;
      },
      {} as { [name: string]: string }
    );
    this.router.navigate(['.'], {
      relativeTo: this.route,
      onSameUrlNavigation: 'reload',
      queryParams: {
        query: this.query,
        page: 1,
        filter: this.stringifyFilters(newFilters),
      },
      state: {
        filters: JSON.stringify(newFilters),
      },
    });
  }

  stringifyFilters(filters: { [name: string]: string }): string {
    let results: string[] = [];
    for (let facet in filters) {
      if (filters[facet]) {
        results.push(`${facet}=${filters[facet]}`);
      }
    }
    return results.join(',');
  }

  onGotoHashTag(tag: string) {
    this.onSearch('#' + tag);
  }

  gotoGeminiChat() {
    if (!this.isUserLoggedIn()) {
      this.loginDialog.toggle();
      return;
    }
    this.router.navigate(['/chat'], {
      relativeTo: this.route,
      queryParams: {
        query: this.query,
        filter: this.filter,
      },
    });
  }
}
