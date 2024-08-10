import { TestBed } from '@angular/core/testing';

import { SearchService } from './search.service';
import {
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http';

describe('SearchService', () => {
  let service: SearchService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [provideHttpClient(withInterceptorsFromDi())],
    });
    service = TestBed.inject(SearchService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('search return success', () => {
    return service.search('0', {}).then(data => {
      expect(data.found).toBeGreaterThan(0);
    });
  });
});
