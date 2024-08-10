import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SearchViewComponent } from './search-view.component';
import {
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http';
import { providersForTest } from '../../testing';
import { provideMockStore } from '@ngrx/store/testing';
import { initAppState } from '../../state/state';
import { selectAppState } from '../../state/selectors';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

describe('SearchViewComponent', () => {
  let component: SearchViewComponent;
  let fixture: ComponentFixture<SearchViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SearchViewComponent, NoopAnimationsModule],
      providers: [
        ...providersForTest,
        provideHttpClient(withInterceptorsFromDi()),
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

    fixture = TestBed.createComponent(SearchViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
