import { NgFor } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatToolbarModule } from '@angular/material/toolbar';
import { Router } from '@angular/router';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { DropdownChangeEvent, DropdownModule } from 'primeng/dropdown';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { ScrollPanelModule } from 'primeng/scrollpanel';
import { EventLoggerService } from '../../providers/event-logger.service';
import { Facet } from '../../providers/search';
import { FacetCountPipe } from '../../utils/facet-count.pipe';
import { FacetFieldNamePipe } from '../../utils/facet-field-name.pipe';
import { FacetValuePipe } from '../../utils/facet-value.pipe';
import { UserButtonComponent } from '../user-button/user-button.component';

export interface FacetChange {
  facet: string;
  value: string;
}

@Component({
  selector: 'app-search-bar',
  standalone: true,
  imports: [
    DropdownModule,
    FacetCountPipe,
    FacetFieldNamePipe,
    FacetValuePipe,
    FormsModule,
    IconFieldModule,
    InputIconModule,
    InputTextModule,
    MatChipsModule,
    MatToolbarModule,
    NgFor,
    ProgressSpinnerModule,
    AvatarModule,
    ButtonModule,
    ScrollPanelModule,
    MatButtonModule,
    MatIconModule,
    UserButtonComponent,
  ],
  templateUrl: './search-bar.component.html',
  styleUrl: './search-bar.component.scss',
})
export class SearchBarComponent {
  @Input({ transform: trimString }) query = '';
  @Input() facets?: Facet[] = [];
  @Input() filters: FacetChange[] = [];
  @Input() loading: boolean = false;
  @Output() queryChange = new EventEmitter<string>();
  @Output() onSearch = new EventEmitter<string>();
  @Output() onFacetChange = new EventEmitter<FacetChange>();

  constructor(
    private router: Router,
    private logger: EventLoggerService
  ) {}

  onSearchClick() {
    let query = trimString(this.query);
    if (query === '') {
      return;
    }
    this.query = query;
    this.onSearch.emit(query);
  }

  onFacetChangeHandler(event: DropdownChangeEvent, facet: string) {
    this.logger.logFacet(facet, event.value);
    this.onFacetChange.emit({
      facet,
      value: event.value,
    });
  }

  goHome() {
    this.router.navigate(['/']);
  }

  removeFilter(event: FacetChange) {
    this.onFacetChange.emit({
      facet: event.facet,
      value: '',
    });
  }
}

function trimString(value: string | undefined) {
  return value?.trim() ?? '';
}
