import { Injectable } from '@angular/core';
import { Analytics, logEvent } from '@angular/fire/analytics';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class EventLoggerService {
  constructor(private analytics: Analytics) {}

  logSearch(keyword: string) {
    this.log('search', { keyword });
  }

  logFacet(facet: string, value: string) {
    this.log('facet', { facet, value });
  }

  logAiSummarize(docType: string) {
    this.log('ai_summarize', { docType });
  }

  logClickDescription(docType: string) {
    this.log('click_description', { docType });
  }

  logEvent(event: string) {
    this.log(event);
  }

  private log(eventName: string, params?: Record<string, any>) {
    if (environment.production) {
      logEvent(this.analytics, eventName, params);
    } else {
      console.log(eventName, params);
    }
  }
}
