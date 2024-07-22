import { HttpClientModule } from '@angular/common/http';
import { Component, Inject, inject } from '@angular/core';
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
import { environment } from '../environments/environment';
import { config, dom } from '@fortawesome/fontawesome-svg-core';
import { DOCUMENT } from '@angular/common';

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
  private readonly analytics = environment.production
    ? inject(Analytics)
    : null;
  private readonly isMainPage$ = this.router.events.pipe(
    filter((event): event is NavigationEnd => event instanceof NavigationEnd),
    map((event: NavigationEnd) => event.url === '/'),
    startWith(true)
  );

  isMainPage = toSignal(this.isMainPage$);

  constructor(@Inject(DOCUMENT) private document: Document) {
    config.autoAddCss = false;
    let head = this.document.getElementsByTagName('head')[0];
    let styleNode = this.document.createElement('style');
    styleNode.innerHTML = dom.css(); // grab FA's CSS
    head.appendChild(styleNode);
  }
}
