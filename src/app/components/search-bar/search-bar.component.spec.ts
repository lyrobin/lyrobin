import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SearchBarComponent } from './search-bar.component';
import { provideMockStore } from '@ngrx/store/testing';
import { providersForTest } from '../../testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { initAppState } from '../../state/state';
import { selectAppState } from '../../state/selectors';

describe('SearchBarComponent', () => {
  let component: SearchBarComponent;
  let fixture: ComponentFixture<SearchBarComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SearchBarComponent, NoopAnimationsModule],
      providers: [
        provideMockStore({
          initialState: initAppState,
          selectors: [
            {
              selector: selectAppState,
              value: initAppState,
            },
          ],
        }),
        ...providersForTest,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SearchBarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
