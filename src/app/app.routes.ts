import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () =>
      import('./pages/home/home.component').then(c => c.HomeComponent),
  },
  {
    path: 'search',
    loadComponent: () =>
      import('./pages/search-view/search-view.component').then(
        c => c.SearchViewComponent
      ),
  },
  {
    path: 'news',
    loadComponent: () =>
      import('./pages/news/news.component').then(c => c.NewsComponent),
  },
  {
    path: 'privacy',
    loadComponent: () =>
      import('./pages/privacy/privacy.component').then(c => c.PrivacyComponent),
  },
  {
    path: '**',
    redirectTo: 'search',
  },
];
