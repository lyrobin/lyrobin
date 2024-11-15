import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import {
  EnhancedGenerateContentResponse,
  GoogleGenerativeAI,
} from '@google/generative-ai';
import { Store } from '@ngrx/store';
import { from, lastValueFrom, Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { selectChatHistory, selectGeminiKey } from '../state/selectors';
import { Document } from './search';

@Injectable({
  providedIn: 'root',
})
export class AicoreService {
  private readonly apiUrl = environment.apiUrl;
  private readonly geminiKey = this.store.selectSignal(selectGeminiKey);
  private readonly history = this.store.selectSignal(selectChatHistory);

  constructor(
    private http: HttpClient,
    private store: Store
  ) {}

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

  chat(message: string): Promise<Observable<EnhancedGenerateContentResponse>> {
    const key = this.geminiKey();
    if (!key) {
      return Promise.reject('Gemini key not found.');
    }
    const genAI = new GoogleGenerativeAI(key);
    const model = genAI.getGenerativeModel({
      model: 'gemini-1.5-flash',
      systemInstruction: `
      你是立院知更這個網站的AI助理。提供給你的資料庫來自該網站的搜尋結果，請依照提供的訊息來回答問題。注意:
      1. 若無法從資料中找到答案，就委婉的不要回答
      2. 若是使用者的問題和資料的內容無關，也請不要回答，並說明這不是你的能力範圍。
      3. 當無法回答問題時，提示："您可以改變搜尋的關鍵字，來獲得更多資訊"`,
    });
    const chat = model.startChat({
      history:
        this.history()?.map(h => {
          return {
            role: h.role,
            parts: [
              {
                text: h.message,
              },
            ],
          };
        }) ?? [],
    });
    return chat.sendMessageStream(message).then(result => from(result.stream));
  }
}
