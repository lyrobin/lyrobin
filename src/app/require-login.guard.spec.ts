import { TestBed } from '@angular/core/testing';
import { CanActivateFn } from '@angular/router';

import { requireLoginGuard } from './require-login.guard';

describe('requireLoginGuard', () => {
  const executeGuard: CanActivateFn = (...guardParameters) => 
      TestBed.runInInjectionContext(() => requireLoginGuard(...guardParameters));

  beforeEach(() => {
    TestBed.configureTestingModule({});
  });

  it('should be created', () => {
    expect(executeGuard).toBeTruthy();
  });
});
