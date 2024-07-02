import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatToolbarModule } from '@angular/material/toolbar';
import { DropdownModule } from 'primeng/dropdown';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { Facet } from '../../providers/search';
import { FacetCountPipe } from '../../utils/facet-count.pipe';
import {NgFor} from '@angular/common';

@Component({
  selector: 'app-search-bar',
  standalone: true,
  imports: [
    DropdownModule,
    FormsModule,
    IconFieldModule,
    InputIconModule,
    InputTextModule,
    MatToolbarModule,
    FacetCountPipe,
    NgFor
  ],
  templateUrl: './search-bar.component.html',
  styleUrl: './search-bar.component.scss',
})
export class SearchBarComponent{
  @Input({transform: trimString}) query = '';
  @Input() facets?: Facet[] = [];
  @Output() queryChange = new EventEmitter<string>();
  @Output() onSearch = new EventEmitter<string>();

  onSearchClick() {
    let query = trimString(this.query);
    if (query === '') {
      return;
    }
    this.query = query;
    this.onSearch.emit(query);
  }
}

function trimString(value: string | undefined) {
  return value?.trim() ?? '';
}
