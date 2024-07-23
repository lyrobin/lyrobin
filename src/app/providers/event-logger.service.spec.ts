import { TestBed } from '@angular/core/testing';

import { EventLoggerService } from './event-logger.service';

describe('EventLoggerService', () => {
  let service: EventLoggerService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(EventLoggerService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
