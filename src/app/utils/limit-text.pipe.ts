import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'limitText',
  standalone: true,
})
export class LimitTextPipe implements PipeTransform {
  transform(value: string, limit: number): string {
    if (value.length > limit) {
      return value.substring(0, limit) + '...';
    }
    return value;
  }
}
