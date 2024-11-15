import { Injectable } from '@angular/core';
import { Auth } from '@angular/fire/auth';
import { environment } from './../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class UserService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private auth: Auth) {}

  getUserGeminiKey(): Promise<string> {
    return (
      this.auth.currentUser?.getIdToken().then(token =>
        fetch(`${this.apiUrl}/users/gemini-key`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          mode: 'cors',
        }).then(res => res.text())
      ) || Promise.reject('User not logged in.')
    );
  }

  setUserGeminiKey(key: string): Promise<void> {
    return (
      this.auth.currentUser?.getIdToken().then(token =>
        fetch(`${this.apiUrl}/users/gemini-key`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          mode: 'cors',
          body: JSON.stringify({ key }),
        }).then(res => {
          if (!res.ok) {
            return res.text().then(err => Promise.reject(err));
          }
          return Promise.resolve();
        })
      ) || Promise.reject('User not logged in.')
    );
  }
}
