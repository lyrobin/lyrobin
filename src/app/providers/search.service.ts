import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { lastValueFrom } from 'rxjs';
import { environment } from './../../environments/environment';
import { LegislatorRemark, SearchResult } from './search';

@Injectable({
  providedIn: 'root',
})
export class SearchService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  search(q: string, filter?: string, page: number = 1): Promise<SearchResult> {
    return lastValueFrom(
      this.http.get<SearchResult>(`${this.apiUrl}/search`, {
        params: {
          q,
          page,
          ...(filter !== undefined && { filter }),
        },
      })
    );
  }

  legislator(name: string): Promise<LegislatorRemark | null> {
    return lastValueFrom(
      this.http.get<LegislatorRemark>(`${this.apiUrl}/ai/legislator`, {
        params: {
          name,
        },
      })
    );
  }
}
