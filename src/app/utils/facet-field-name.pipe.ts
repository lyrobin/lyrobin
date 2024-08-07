import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'facetFieldName',
  standalone: true,
})
export class FacetFieldNamePipe implements PipeTransform {
  transform(value: string, ...args: unknown[]): string {
    switch (value) {
      case 'doc_type': {
        return '類型';
      }
      case 'meeting_unit': {
        return '委員會';
      }
      case 'chairman': {
        return '召集人';
      }
      case 'status': {
        return '進度';
      }
      case 'proposers': {
        return '提案人';
      }
      case 'sponsors': {
        return '連署人';
      }
      case 'member': {
        return '發言人';
      }
      case 'legislator': {
        return '委員/黨團';
      }
      default: {
        return '';
      }
    }
  }
}
