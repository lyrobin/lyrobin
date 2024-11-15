import { Component, OnInit } from '@angular/core';
import { SearchBarComponent } from '../../components/search-bar/search-bar.component';
import { ActivatedRoute, Router } from '@angular/router';
import { DocumentService } from '../../providers/document.service';
import { CardModule } from 'primeng/card';
import { MarkdownModule } from 'ngx-markdown';
import { MarkdownSanitizePipe } from '../../utils/markdown-sanitize.pipe';
import { HttpClient } from '@angular/common/http';
import { lastValueFrom } from 'rxjs';

@Component({
  selector: 'app-privacy',
  standalone: true,
  imports: [
    SearchBarComponent,
    CardModule,
    MarkdownModule,
    MarkdownSanitizePipe,
  ],
  templateUrl: './privacy.component.html',
  styleUrl: './privacy.component.scss',
})
export class PrivacyComponent implements OnInit {
  privacy: string = '';

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    lastValueFrom(
      this.http.get('assets/privacy_policy.md', { responseType: 'text' })
    ).then(response => (this.privacy = response));
  }

  onSearch(query: string) {
    this.router.navigate(['search'], {
      relativeTo: this.route,
      queryParams: { query, page: 1 },
    });
  }
}
