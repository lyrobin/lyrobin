import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideMockStore } from '@ngrx/store/testing';

import { SearchResultsComponent } from './search-results.component';
import {
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http';

import { providersForTest } from '../../testing';
import {
  FirebaseApp,
  initializeApp,
  provideFirebaseApp,
} from '@angular/fire/app';
import { provideStorage, Storage } from '@angular/fire/storage';
import { getStorage } from 'firebase/storage';
import { provideAuth } from '@angular/fire/auth';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import {
  BrowserAnimationsModule,
  NoopAnimationsModule,
} from '@angular/platform-browser/animations';

describe('SearchResultsComponent', () => {
  let component: SearchResultsComponent;
  let fixture: ComponentFixture<SearchResultsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SearchResultsComponent, NoopAnimationsModule],
      providers: [
        ...providersForTest,
        provideHttpClient(withInterceptorsFromDi()),
        provideMockStore(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SearchResultsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
