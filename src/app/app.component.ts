import { Component, OnInit, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterOutlet,
} from '@angular/router';
import { filter, map, startWith } from 'rxjs';
import { AngularIconComponent } from './components/icons/angular-icon.component';
import { FirebaseIconComponent } from './components/icons/firebase-icon.component';
import { ArrowBackIconComponent } from './components/icons/arrow-back-icon.component';
import { HttpClientModule } from '@angular/common/http';
import { Analytics, logEvent } from '@angular/fire/analytics';

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
export class AppComponent implements OnInit {
  private readonly router = inject(Router);
  private readonly isMainPage$ = this.router.events.pipe(
    filter((event): event is NavigationEnd => event instanceof NavigationEnd),
    map((event: NavigationEnd) => event.url === '/'),
    startWith(true)
  );

  constructor(private analytics: Analytics) {}
  ngOnInit(): void {
    console.log(this.analytics.app);
    logEvent(this.analytics, 'page_view');
  }

  isMainPage = toSignal(this.isMainPage$);
}
