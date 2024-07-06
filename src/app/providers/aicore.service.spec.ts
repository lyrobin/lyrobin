import { TestBed } from '@angular/core/testing';

import { AicoreService } from './aicore.service';

describe('AicoreService', () => {
  let service: AicoreService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(AicoreService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
