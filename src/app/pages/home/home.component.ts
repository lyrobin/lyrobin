import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatChipsModule } from '@angular/material/chips';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { ExternalLinkDirective } from '../../directives/external-link.directive';
import { MatCardModule } from '@angular/material/card';
import { CardModule } from 'primeng/card';

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
  ],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
  host: {
    class: 'home-container flex flex-column',
  },
})
export class HomeComponent {
  constructor(
    private router: Router,
    private route: ActivatedRoute
  ) {}

  @Input({ transform: trimString }) query = '';
  hints: string[] = ['綠能', '國會改革', '健保', '食安'];

  onSearchClick() {
    console.log(`click ${this.query}`);
    this.goto(this.query);
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
