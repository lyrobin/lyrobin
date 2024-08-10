import { TestBed } from '@angular/core/testing';

import { DocumentService } from './document.service';
import { providersForTest } from '../testing';

describe('DocumentService', () => {
  let service: DocumentService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [...providersForTest],
    });
    service = TestBed.inject(DocumentService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
