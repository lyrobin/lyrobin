import { Component, ElementRef, Input, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatChipsModule } from '@angular/material/chips';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import { faAngleDoubleDown } from '@fortawesome/free-solid-svg-icons';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
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

  hints: string[] = ['綠能', '國會改革', '健保', '食安'];
  faAngleDoubleDown = faAngleDoubleDown;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private logger: EventLoggerService
  ) {}

  onSearchClick() {
    console.log(`click ${this.query}`);
    this.goto(this.query);
  }

  onScrollDown() {
    console.log('scroll down');
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
