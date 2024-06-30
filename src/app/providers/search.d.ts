interface FacetCount {
    value: string;
    count: number;
}

interface Facet {
    field: string;
    counts: FacetCount[];
}

interface Document {
    path: string;
    name: string;
    content: string;
    url: string;
}

interface SearchResult {
    facet: Facet[];
    hits: Document[];
    found: number;
}