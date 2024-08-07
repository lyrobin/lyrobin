import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { parse } from 'date-fns';
import { lastValueFrom } from 'rxjs';
import { environment } from './../../environments/environment';
import { Facet, LegislatorRemark, SearchResult } from './search';

@Injectable({
  providedIn: 'root',
})
export class SearchService {
  private readonly apiUrl = environment.apiUrl;

  private readonly legislatorFields = [
    'chairman',
    'proposers',
    'sponsors',
    'member',
  ];

  constructor(private http: HttpClient) {}

  search(
    q: string,
    filters: { [name: string]: string },
    page: number = 1
  ): Promise<SearchResult> {
    const filter = this.toFilterString(filters);
    return lastValueFrom(
      this.http.get<SearchResult>(`${this.apiUrl}/search`, {
        params: {
          q,
          page,
          ...(filter !== undefined && { filter }),
        },
      })
    ).then(result => {
      result.facet = this.groupFacets(result.facet);
      return result;
    });
  }

  private toFilterString(filters: { [name: string]: string }): string {
    let queries: string[] = [];
    for (let facet in filters) {
      if (facet === 'legislator' && filters[facet]) {
        const q = this.legislatorFields
          .map(f => `${f}: \`${filters[facet]}*\``)
          .join('||');
        queries.push(`(${q})`);
      } else if (facet === 'created_date' && filters[facet]) {
        let [start, end] = filters[facet].split('-');
        start = start.trim();
        end = end.trim();
        const s = parse(start, 'yyyy年MM月dd日', new Date()).getTime() / 1000;
        const e = parse(end, 'yyyy年MM月dd日', new Date()).getTime() / 1000;
        queries.push(`created_date:[${s}..${e}]`);
      } else if (filters[facet]) {
        queries.push(`${facet}:=\`${filters[facet]}\``);
      }
    }
    return queries.join('&&');
  }
  private groupFacets(facets: Facet[]): Facet[] {
    if (!facets) {
      return [];
    }
    const groupedFacets: Facet[] = [];
    const groupedFields = [...this.legislatorFields, 'legislator'];
    const valueCounts = new Map<string, number>();
    facets
      .filter(facet => groupedFields.includes(facet.field))
      .forEach(facet => {
        facet.counts.forEach(count => {
          const name = count.value.replace(/委員$/, '');
          valueCounts.set(name, (valueCounts.get(name) || 0) + count.count);
        });
      });
    const uniqueCounts = Array.from(valueCounts.entries())
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => b.value.localeCompare(a.value));
    groupedFacets.push({ field: 'legislator', counts: uniqueCounts });
    const remainingFacets = facets.filter(
      facet => !groupedFields.includes(facet.field)
    );
    groupedFacets.push(...remainingFacets);
    return groupedFacets;
  }

  legislator(name: string): Promise<LegislatorRemark | null> {
    return lastValueFrom(
      this.http.get<LegislatorRemark>(`${this.apiUrl}/ai/legislator`, {
        params: {
          name,
        },
      })
    );
  }
}
