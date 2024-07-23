import { Component, Input } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  FacetChange,
  SearchBarComponent,
} from '../../components/search-bar/search-bar.component';
import { SearchResultsComponent } from '../../components/search-results/search-results.component';
import { EventLoggerService } from '../../providers/event-logger.service';
import { Facet, SearchResult } from '../../providers/search';
import { SearchService } from '../../providers/search.service';
import { translate } from '../../utils/facet-value.pipe';

@Component({
  selector: 'app-search-view',
  standalone: true,
  imports: [SearchBarComponent, SearchResultsComponent],
  templateUrl: './search-view.component.html',
  styleUrl: './search-view.component.scss',
})
export class SearchViewComponent {
  @Input() query?: string;
  @Input() page?: number;
  @Input() filter?: string;
  result?: SearchResult;
  loading: boolean = true;

  constructor(
    private searchService: SearchService,
    private router: Router,
    private route: ActivatedRoute,
    private logger: EventLoggerService
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
      .search(this.query ?? '', this.filterQuery, this.currentPage)
      .then(result => {
        this.result = result;
      })
      .finally(() => {
        this.logger.logSearch(this.query ?? '');
        this.loading = false;
      });
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

  get filterQuery(): string {
    let queries: string[] = [];
    for (let facet in this.filters) {
      if (this.filters[facet]) {
        queries.push(`${facet}:=${this.filters[facet]}`);
      }
    }
    return queries.join('&&');
  }

  get filterArray(): string[] {
    return Object.entries(this.filters).map(([_, value]) => translate(value));
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
}
