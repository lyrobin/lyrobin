import { Component, Inject, OnInit, PLATFORM_ID } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { SearchService } from '../../providers/search.service';
import { MatChipsModule } from '@angular/material/chips';
import { isPlatformBrowser } from '@angular/common';

@Component({
  selector: 'app-keywords',
  standalone: true,
  imports: [MatChipsModule],
  templateUrl: './keywords.component.html',
  styleUrl: './keywords.component.scss',
  host: { ngSkipHydration: 'true' },
})
export class KeywordsComponent implements OnInit {
  private isBrowser: boolean;
  hints: string[] = [];

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private searchService: SearchService,
    @Inject(PLATFORM_ID) platformId: any
  ) {
    this.isBrowser = isPlatformBrowser(platformId);
  }

  ngOnInit(): void {
    if (!this.isBrowser) {
      return;
    }
    this.searchService
      .hotKeywords()
      .then(keywords => {
        this.hints.splice(0, this.hints.length, ...keywords);
      })
      .catch(err => {
        this.hints.splice(
          0,
          this.hints.length,
          ...['綠能', '國會改革', '健保', '食安']
        );
      });
  }

  goto(query: string) {
    if (query === '') {
      return;
    }
    this.router.navigate(['search'], {
      relativeTo: this.route,
      onSameUrlNavigation: 'reload',
      queryParams: { query: query, page: 1 },
    });
  }
}
