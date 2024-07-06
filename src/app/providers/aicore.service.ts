import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { environment } from '../../environments/environment';
import { Document } from './search';
import { lastValueFrom } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class AicoreService {
  private readonly apiUrl = environment.apiUrl;
  constructor(private http: HttpClient) {}

  summary(doc: Document): Promise<string> {
    return lastValueFrom(
      this.http.get(`${this.apiUrl}/ai/summary`, {
        params: {
          path: encodeURIComponent(doc.path),
        },
        responseType: 'text',
      })
    );
  }
}
