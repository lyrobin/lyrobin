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
    path: '**',
    redirectTo: 'search',
  },
];
