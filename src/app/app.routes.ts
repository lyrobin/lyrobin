import { Routes } from '@angular/router';
import { requireLoginGuard } from './require-login.guard';

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
    path: 'user',
    loadComponent: () =>
      import('./pages/user/user.component').then(c => c.UserComponent),
    canActivate: [requireLoginGuard],
  },
  {
    path: 'chat',
    loadComponent: () =>
      import('./pages/chat/chat.component').then(c => c.ChatComponent),
  },
  {
    path: '**',
    redirectTo: 'search',
  },
];
