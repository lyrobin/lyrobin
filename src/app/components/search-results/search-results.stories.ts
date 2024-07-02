import type { Meta, StoryObj } from '@storybook/angular';
import { SearchResultsComponent } from './search-results.component';
import { argsToTemplate, applicationConfig } from '@storybook/angular';
import { Document } from '../../providers/search';
import { action } from '@storybook/addon-actions';
import { appConfig } from '../../app.config';

const actionsData = {
  onPageChange: action('onPageChange'),
};

const meta: Meta<SearchResultsComponent> = {
  title: 'search results',
  component: SearchResultsComponent,
  decorators: [applicationConfig(appConfig)],
  tags: ['autodocs'],
  render: args => ({
    props: {
      ...args,
      onPageChange: actionsData.onPageChange,
    },
    template: `<app-search-results ${argsToTemplate(args)}></app-search-results>`,
  }),
};

export default meta;
type Story = StoryObj<SearchResultsComponent>;

export const Primary: Story = {
  args: {
    result: {
      facet: [],
      found: 100,
      hits: Array(10)
        .fill(0)
        .map(
          (_, i) =>
            ({
              name: `document-${i}`,
              content: 'document content',
            }) as Document
        ),
    },
  },
};
