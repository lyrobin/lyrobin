import { Injectable } from '@angular/core';
import {environment} from "./../../environments/environment"
import { HttpClient } from '@angular/common/http';
import {lastValueFrom} from 'rxjs';
import { SearchResult } from './search';


@Injectable({
  providedIn: 'root'
})
export class SearchService {

  private readonly apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) { }

  search(q: string, filter?: string, page: number = 1): Promise<SearchResult> {
    return lastValueFrom(this.http.get<SearchResult>(`${this.apiUrl}/search`, {
      params: {
        q,
        page,
        ...(filter !== undefined && {filter})
      }
    }));
  }
}
