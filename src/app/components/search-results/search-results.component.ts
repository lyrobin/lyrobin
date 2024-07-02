import { Component, Input, Output, EventEmitter } from '@angular/core';
import { SearchResult, Document } from '../../providers/search';
import { DataViewModule } from 'primeng/dataview';
import { DataViewPageEvent } from 'primeng/dataview';
import { NgFor } from '@angular/common';

@Component({
  selector: 'app-search-results',
  standalone: true,
  imports: [DataViewModule, NgFor],
  templateUrl: './search-results.component.html',
  styleUrl: './search-results.component.scss',
})
export class SearchResultsComponent {
  @Input() result?: SearchResult;
  @Input() rows: number = 20;
  @Input() page: number = 1;
  @Output() onPageChange = new EventEmitter<number>();

  get totalRecords(): number {
    return this.result?.found || 0;
  }

  get hits(): Document[] {
    return this.result?.hits || [];
  }

  get first(): number {
    return Math.max((this.page - 1) * this.rows, 0);
  }

  onPage(event: DataViewPageEvent) {
    this.onPageChange.emit(Math.floor(event.first / event.rows) + 1);
  }
}
