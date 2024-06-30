import { TestBed } from '@angular/core/testing';

import { SearchService } from './search.service';
import { HttpClientModule } from '@angular/common/http';

describe('SearchService', () => {
  let service: SearchService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientModule],
    });
    service = TestBed.inject(SearchService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('search return success', () => {
    return service.search("0").then(data => {
      expect(data.found).toBeGreaterThan(0);
    });
  });
});
