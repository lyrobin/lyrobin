import { Component, Input, OnInit } from '@angular/core';
import { SearchBarComponent } from '../../components/search-bar/search-bar.component';
import { SearchResultsComponent } from '../../components/search-results/search-results.component';
import { SearchService } from '../../providers/search.service';
import { SearchResult } from '../../providers/search';
import {
  ActivatedRoute,
  NavigationEnd,
  NavigationStart,
  Router,
} from '@angular/router';
import { filter } from 'rxjs';
import e from 'express';

@Component({
  selector: 'app-search-view',
  standalone: true,
  imports: [SearchBarComponent, SearchResultsComponent],
  templateUrl: './search-view.component.html',
  styleUrl: './search-view.component.scss',
})
export class SearchViewComponent implements OnInit {
  @Input() query?: string;
  @Input() page?: number;
  result?: SearchResult;

  constructor(
    private searchService: SearchService,
    private router: Router,
    private route: ActivatedRoute
  ) {
    this.route.queryParams.subscribe(params => {
      this.query = params['query'];
      this.page = params['page'];
      this.reload();
    });
  }

  ngOnInit(): void {
    this.reload();
  }

  reload() {
    this.searchService
      .search(this.query ?? '', undefined, this.currentPage)
      .then(result => {
        this.result = result;
      });
  }

  get currentPage(): number {
    return (this.page || 0) <= 0 ? 1 : this.page!;
  }

  onPageChange(page: number) {
    this.router.navigate(['.'], {
      relativeTo: this.route,
      onSameUrlNavigation: 'reload',
      queryParams: { query: this.query, page: page },
    });
  }

  onSearch(query: string) {
    this.router.navigate(['.'], {
      relativeTo: this.route,
      onSameUrlNavigation: 'reload',
      queryParams: { query: query, page: 1 },
    });
  }
}
