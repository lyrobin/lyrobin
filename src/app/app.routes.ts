import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'search',
    pathMatch: 'full',
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
