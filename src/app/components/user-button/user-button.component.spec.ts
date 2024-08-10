import { ComponentFixture, TestBed } from '@angular/core/testing';

import { provideMockStore } from '@ngrx/store/testing';
import { selectAppState } from '../../state/selectors';
import { initAppState } from '../../state/state';
import { providersForTest } from '../../testing';
import { UserButtonComponent } from './user-button.component';

describe('UserButtonComponent', () => {
  let component: UserButtonComponent;
  let fixture: ComponentFixture<UserButtonComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UserButtonComponent],
      providers: [
        ...providersForTest,
        provideMockStore({
          initialState: initAppState,
          selectors: [
            {
              selector: selectAppState,
              value: initAppState,
            },
          ],
        }),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(UserButtonComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
