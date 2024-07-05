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
      default: {
        return '';
      }
    }
  }
}
