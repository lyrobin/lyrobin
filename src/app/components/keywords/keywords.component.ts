import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { SearchService } from '../../providers/search.service';
import { MatChipsModule } from '@angular/material/chips';

@Component({
  selector: 'app-keywords',
  standalone: true,
  imports: [MatChipsModule],
  templateUrl: './keywords.component.html',
  styleUrl: './keywords.component.scss',
  host: { ngSkipHydration: 'true' },
})
export class KeywordsComponent implements OnInit {
  hints: string[] = [];

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private searchService: SearchService
  ) {}

  ngOnInit(): void {
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
