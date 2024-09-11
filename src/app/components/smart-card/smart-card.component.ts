import { DecimalPipe, NgIf } from '@angular/common';
import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
} from '@angular/core';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import {
  faAngleDoubleDown,
  faAngleDoubleUp,
  IconDefinition,
} from '@fortawesome/free-solid-svg-icons';
import { Store } from '@ngrx/store';
import { MarkdownModule } from 'ngx-markdown';
import { AvatarModule } from 'primeng/avatar';
import { BadgeModule } from 'primeng/badge';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DividerModule } from 'primeng/divider';
import { FieldsetModule } from 'primeng/fieldset';
import { ScrollPanelModule } from 'primeng/scrollpanel';
import { TagModule } from 'primeng/tag';
import { LegislatorRemark, Topic } from '../../providers/search';
import { isUserLoggedIn } from '../../state/selectors';

@Component({
  selector: 'app-smart-card',
  standalone: true,
  imports: [
    NgIf,
    DecimalPipe,
    CardModule,
    AvatarModule,
    FieldsetModule,
    BadgeModule,
    FontAwesomeModule,
    ButtonModule,
    DividerModule,
    MarkdownModule,
    ScrollPanelModule,
    TagModule,
  ],
  templateUrl: './smart-card.component.html',
  styleUrl: './smart-card.component.scss',
})
export class SmartCardComponent implements OnChanges {
  @Input() show: boolean = false;
  @Input() legislatorRemark?: LegislatorRemark;
  @Input() topic?: Topic;
  @Output() onSearch = new EventEmitter<string>();
  readonly isUserLoggedIn$ = this.store.selectSignal(isUserLoggedIn);

  expanded: boolean = false;

  constructor(private store: Store) {}

  ngOnChanges(changes: SimpleChanges): void {
    this.expanded = false;
  }
  get maxRemarks(): number {
    return this.expanded ? 20 : 3;
  }

  get expandIcon(): IconDefinition {
    return this.expanded ? faAngleDoubleUp : faAngleDoubleDown;
  }

  get hasMore(): boolean {
    return (this.legislatorRemark?.remarks.length || 0) > 3;
  }

  get showLegislator(): boolean {
    return this.show && this.legislatorRemark !== undefined;
  }

  get showTopic(): boolean {
    return this.show && this.topic !== undefined;
  }

  gotoExternal(url: string) {
    window.open(url, '_blank');
  }

  gotoExpand() {
    this.expanded = !this.expanded;
  }

  search(q: string) {
    this.onSearch.emit(q);
  }
}
