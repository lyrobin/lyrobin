import { TestBed } from '@angular/core/testing';

import { VideoDownloaderService } from './video-downloader.service';

describe('VideoDownloaderService', () => {
  let service: VideoDownloaderService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(VideoDownloaderService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
