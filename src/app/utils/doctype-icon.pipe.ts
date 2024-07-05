import { Pipe, PipeTransform } from '@angular/core';
import { Document } from '../providers/search';

@Pipe({
  name: 'doctypeIcon',
  standalone: true,
})
export class DoctypeIconPipe implements PipeTransform {
  transform(doc: Document, ...args: unknown[]): string {
    switch (doc.doctype) {
      case 'meeting': {
        return 'groups';
      }
      case 'proceeding': {
        return 'topic';
      }
      case 'video': {
        return 'video_file';
      }
      case 'meetingfile': {
        return 'description';
      }
      case 'attachment': {
        return 'attachment';
      }
      default: {
        return 'help';
      }
    }
  }
}
