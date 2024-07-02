export interface FacetCount {
  value: string;
  count: number;
}

export interface Facet {
  field: string;
  counts: FacetCount[];
}

export interface Document {
  path: string;
  name: string;
  content: string;
  url: string;
}

export interface SearchResult {
  facet: Facet[];
  hits: Document[];
  found: number;
}
