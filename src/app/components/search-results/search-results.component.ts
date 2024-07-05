import { NgFor, NgIf } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CardModule } from 'primeng/card';
import { DataViewModule } from 'primeng/dataview';
import { PaginatorModule, PaginatorState } from 'primeng/paginator';
import { ScrollPanelModule } from 'primeng/scrollpanel';
import { Document, SearchResult } from '../../providers/search';
import { SkeletonModule } from 'primeng/skeleton';
import { MatIconModule } from '@angular/material/icon';
import { DoctypeIconPipe } from '../../utils/doctype-icon.pipe';

@Component({
  selector: 'app-search-results',
  standalone: true,
  imports: [
    CardModule,
    DataViewModule,
    NgFor,
    NgIf,
    PaginatorModule,
    ScrollPanelModule,
    SkeletonModule,
    MatIconModule,
    DoctypeIconPipe,
  ],
  templateUrl: './search-results.component.html',
  styleUrl: './search-results.component.scss',
})
export class SearchResultsComponent {
  @Input() result?: SearchResult;
  @Input() rows: number = 20;
  @Input() page: number = 1;
  @Input() loading: boolean = false;
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

  onPage(event: PaginatorState) {
    this.onPageChange.emit(
      Math.floor((event.first ?? 0) / (event.rows ?? 1)) + 1
    );
  }
}
