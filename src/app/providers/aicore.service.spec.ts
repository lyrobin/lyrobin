import { TestBed } from '@angular/core/testing';

import { AicoreService } from './aicore.service';
import { providersForTest } from '../testing';
import {
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http';

describe('AicoreService', () => {
  let service: AicoreService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        ...providersForTest,
        provideHttpClient(withInterceptorsFromDi()),
      ],
    });
    service = TestBed.inject(AicoreService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
