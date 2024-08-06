import { Injectable } from '@angular/core';
import { Auth } from '@angular/fire/auth';
import { environment } from './../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class DocumentService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private auth: Auth) {}

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
}
