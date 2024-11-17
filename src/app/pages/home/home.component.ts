import { Component, ElementRef, Input, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatChipsModule } from '@angular/material/chips';
import { MatToolbarModule } from '@angular/material/toolbar';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import { faAngleDoubleDown } from '@fortawesome/free-solid-svg-icons';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { KeywordsComponent } from '../../components/keywords/keywords.component';
import { NavbarButtonComponent } from '../../components/navbar-button/navbar-button.component';
import { UserButtonComponent } from '../../components/user-button/user-button.component';
import { ExternalLinkDirective } from '../../directives/external-link.directive';
import { EventLoggerService } from '../../providers/event-logger.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    RouterLink,
    ExternalLinkDirective,
    InputTextModule,
    ButtonModule,
    FormsModule,
    MatChipsModule,
    IconFieldModule,
    InputIconModule,
    CardModule,
    FontAwesomeModule,
    MatToolbarModule,
    UserButtonComponent,
    NavbarButtonComponent,
    KeywordsComponent,
  ],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
  host: {
    class: 'home-container w-full',
  },
})
export class HomeComponent {
  @Input({ transform: trimString }) query = '';
  @ViewChild('secondPage') secondPage!: ElementRef<HTMLDivElement>;

  faAngleDoubleDown = faAngleDoubleDown;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private logger: EventLoggerService
  ) {}

  onSearchClick() {
    this.goto(this.query);
  }

  onScrollDown() {
    this.secondPage.nativeElement.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  }

  bookMeeting() {
    this.logger.logEvent('book_meeting');
    window.open('https://calendar.app.google/YrNrYZLWvxmT4VvT9', '_blank');
  }

  goto(query: string) {
    if (query === '') {
      return;
    }
    this.router.navigate(['search'], {
      relativeTo: this.route,
      onSameUrlNavigation: 'reload',
      queryParams: { query: query, page: 1 },
    });
  }
}

function trimString(value: string | undefined) {
  return value?.trim() ?? '';
}
