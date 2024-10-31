import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Auth } from '@angular/fire/auth';
import { environment } from './../../environments/environment';
import { NewsReport } from './document';
import { lastValueFrom } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class DocumentService {
  private readonly apiUrl = environment.apiUrl;

  constructor(
    private auth: Auth,
    private http: HttpClient
  ) {}

  getSpeechVideo(docPath: string): Promise<string> {
    docPath = docPath.replace(/^\/+/, '').replace(/\/+$/, '');
    return (
      this.auth.currentUser
        ?.getIdToken()
        .then(token =>
          fetch(`${this.apiUrl}/${docPath}/video`, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
            mode: 'cors',
          })
        )
        .then(res => res.text())
        .then(url => (url !== '' ? url : Promise.reject('File not found.'))) ||
      Promise.reject('User not logged in.')
    );
  }

  getVideoPlaylist(docPath: string): Promise<string> {
    docPath = docPath.replace(/^\/+/, '').replace(/\/+$/, '');
    return (
      this.auth.currentUser
        ?.getIdToken()
        .then(token =>
          fetch(`${this.apiUrl}/${docPath}/playlist`, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
            mode: 'cors',
          })
        )
        .then(res => res.text())
        .then(url => (url !== '' ? url : Promise.reject('File not found.'))) ||
      Promise.reject('User not logged in.')
    );
  }

  getNewsReports(
    startAfter: string | undefined = undefined,
    limit: number = 10
  ): Promise<NewsReport[]> {
    return lastValueFrom(
      this.http.get<NewsReport[]>(`${this.apiUrl}/news`, {
        params: {
          start: startAfter ?? '',
          limit,
        },
      })
    );
  }
}
