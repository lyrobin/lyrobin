import { Pipe, PipeTransform } from '@angular/core';
import { FacetCount } from '../providers/search';

@Pipe({
  name: 'facetCount',
  standalone: true,
})
export class FacetCountPipe implements PipeTransform {
  transform(value: FacetCount[], ...args: unknown[]): string[] {
    return value.map(c => c.value);
  }
}
