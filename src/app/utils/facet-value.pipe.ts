import { Pipe, PipeTransform } from '@angular/core';

interface Option {
  name: string;
  value: string;
}

export function translate(value: string): string {
  switch (value) {
    case 'meetingfile': {
      return '會議文檔';
    }
    case 'meeting': {
      return '議會';
    }
    case 'proceeding': {
      return '關聯文書';
    }
    case 'video': {
      return '影片';
    }
    case 'attachment': {
      return '附件';
    }
    default: {
      return value;
    }
  }
}

@Pipe({
  name: 'facetValue',
  standalone: true,
})
export class FacetValuePipe implements PipeTransform {
  transform(value: string[], ...args: unknown[]): Option[] {
    let results: Option[] = [];
    return value.map(v => ({ name: translate(v), value: v }));
  }
}
