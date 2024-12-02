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

  getTranscript(docPath: string): Promise<string> {
    docPath = docPath.replace(/^\/+/, '').replace(/\/+$/, '');
    if (!this.auth.currentUser) {
      return Promise.reject('User not logged in.');
    }
    return this.auth.currentUser.getIdToken().then(token =>
      fetch(`${this.apiUrl}/${docPath}/transcript`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        mode: 'cors',
      }).then(res => res.text())
    );
  }

  triggerDownloadText(text: string, filename: string) {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
}
