import type { Meta, StoryObj } from '@storybook/angular';
import { SearchBarComponent } from './search-bar.component';
import { argsToTemplate, applicationConfig } from '@storybook/angular';
import { action } from '@storybook/addon-actions';
import { appConfig } from '../../app.config';

const actionsData = {
  onQueryChange: action('onQueryChange'),
  onSearch: action('onSearch'),
};

const meta: Meta<SearchBarComponent> = {
  title: 'search bar',
  component: SearchBarComponent,
  decorators: [applicationConfig(appConfig)],
  tags: ['autodocs'],
  render: args => ({
    props: {
      ...args,
      queryChange: actionsData.onQueryChange,
      onSearch: actionsData.onSearch,
    },
    template: `<app-search-bar ${argsToTemplate(args)}/>`,
  }),
};

export default meta;
type Story = StoryObj<SearchBarComponent>;

export const Primary: Story = {
  args: {
    query: 'query',
  },
};

export const Facet: Story = {
  args: {
    facets: [
      {
        field: 'field',
        counts: [
          {
            value: 'value',
            count: 1,
          },
        ],
      },
    ],
  },
};
