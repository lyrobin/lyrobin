import { Component, OnInit } from '@angular/core';
import { SearchBarComponent } from '../../components/search-bar/search-bar.component';
import { ActivatedRoute, Router } from '@angular/router';
import { NewsReportComponent } from '../../components/news-report/news-report.component';
import { DocumentService } from '../../providers/document.service';
import { NewsReport } from '../../providers/document';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

@Component({
  selector: 'app-news',
  standalone: true,
  imports: [
    SearchBarComponent,
    NewsReportComponent,
    ButtonModule,
    ProgressSpinnerModule,
  ],
  templateUrl: './news.component.html',
  styleUrl: './news.component.scss',
})
export class NewsComponent implements OnInit {
  readonly limit = 10;
  newsReports: NewsReport[] = [];
  hasMore: boolean = true;
  isLoading: boolean = false;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private documentService: DocumentService
  ) {}

  ngOnInit(): void {
    this.documentService.getNewsReports('', this.limit).then(newsReports => {
      this.newsReports.splice(0, this.newsReports.length, ...newsReports);
      if (newsReports.length < this.limit) {
        this.hasMore = false;
      }
    });
  }

  onSearch(query: string) {
    this.router.navigate(['search'], {
      relativeTo: this.route,
      queryParams: { query, page: 1 },
    });
  }

  loadMore() {
    this.isLoading = true;
    this.documentService
      .getNewsReports(
        this.newsReports[this.newsReports.length - 1].id,
        this.limit
      )
      .then(newsReports => {
        this.newsReports.push(...newsReports);
        if (newsReports.length <= 0) {
          this.hasMore = false;
        }
      })
      .finally(() => {
        this.isLoading = false;
      });
  }
}
