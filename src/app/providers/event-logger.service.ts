import { Injectable, inject } from '@angular/core';
import { Analytics, logEvent } from '@angular/fire/analytics';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class EventLoggerService {
  private readonly analytics = environment.production
    ? inject(Analytics)
    : null;

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

  logDownloadVideo(docPath: string, login: boolean) {
    this.log('download_video', { docPath, login });
  }

  logDownloadTranscript(docPath: string, login: boolean) {
    this.log('download_transcript', { docPath, login });
  }

  logEvent(event: string) {
    this.log(event);
  }

  private log(eventName: string, params?: Record<string, any>) {
    if (this.analytics) {
      logEvent(this.analytics, eventName, params);
    } else {
      // TODO: need fix it, don't show this during build time.
      // console.log(eventName, params);
    }
  }
}
