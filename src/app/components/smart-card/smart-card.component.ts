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
import { AvatarModule } from 'primeng/avatar';
import { BadgeModule } from 'primeng/badge';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DividerModule } from 'primeng/divider';
import { FieldsetModule } from 'primeng/fieldset';
import { LegislatorRemark } from '../../providers/search';
import {
  faAngleDoubleDown,
  faAngleDoubleUp,
  IconDefinition,
} from '@fortawesome/free-solid-svg-icons';

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
  ],
  templateUrl: './smart-card.component.html',
  styleUrl: './smart-card.component.scss',
})
export class SmartCardComponent implements OnChanges {
  @Input() show: boolean = false;
  @Input() legislatorRemark?: LegislatorRemark;
  @Output() onSearch = new EventEmitter<string>();

  expanded: boolean = false;

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

  gotoExternal(url: string) {
    window.open(url, '_blank');
  }

  gotoExpand() {
    this.expanded = !this.expanded;
  }

  search(q: string) {
    console.log(q);
    this.onSearch.emit(q);
  }
}
