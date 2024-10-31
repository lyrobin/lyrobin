import { Component, Input, OnInit } from '@angular/core';
import { CardModule } from 'primeng/card';
import { NewsReport } from '../../providers/document';
import { MarkdownComponent } from 'ngx-markdown';
import { CommonModule } from '@angular/common';
import { TagModule } from 'primeng/tag';
import { LimitTextPipe } from '../../utils/limit-text.pipe';
import { ButtonModule } from 'primeng/button';
import { ActivatedRoute, Router } from '@angular/router';
import { filter } from 'rxjs';

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
  ],
  templateUrl: './news-report.component.html',
  styleUrl: './news-report.component.scss',
})
export class NewsReportComponent implements OnInit {
  @Input({ required: true }) newsReport!: NewsReport;
  isExpanded: boolean = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router
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
}
