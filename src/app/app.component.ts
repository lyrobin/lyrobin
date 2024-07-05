import { HttpClientModule } from '@angular/common/http';
import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Analytics } from '@angular/fire/analytics';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterOutlet,
} from '@angular/router';
import { filter, map, startWith } from 'rxjs';
import { AngularIconComponent } from './components/icons/angular-icon.component';
import { ArrowBackIconComponent } from './components/icons/arrow-back-icon.component';
import { FirebaseIconComponent } from './components/icons/firebase-icon.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterOutlet,
    AngularIconComponent,
    FirebaseIconComponent,
    ArrowBackIconComponent,
    RouterLink,
    HttpClientModule,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {
  private readonly router = inject(Router);
  private readonly analytics = inject(Analytics);
  private readonly isMainPage$ = this.router.events.pipe(
    filter((event): event is NavigationEnd => event instanceof NavigationEnd),
    map((event: NavigationEnd) => event.url === '/'),
    startWith(true)
  );

  isMainPage = toSignal(this.isMainPage$);
}
