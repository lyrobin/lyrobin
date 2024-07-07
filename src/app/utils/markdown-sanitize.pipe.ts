import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'markdownSanitize',
  standalone: true,
})
export class MarkdownSanitizePipe implements PipeTransform {
  transform(value: string, ...args: unknown[]): string {
    const re = /\*\*\s*(.+?)\s*\*\*/gi;
    return value.replace(re, ' **$1** ');
  }
}
