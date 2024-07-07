import { MarkdownSanitizePipe } from './markdown-sanitize.pipe';

describe('MarkdownSanitizePipe', () => {
  it('create an instance', () => {
    const pipe = new MarkdownSanitizePipe();
    expect(pipe).toBeTruthy();
  });
});
