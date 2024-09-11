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
  doctype: 'meeting' | 'proceeding' | 'video' | 'meetingfile' | 'attachment';
  created_date: number;
  hashtags: string[];
}

export interface SearchResult {
  facet: Facet[];
  hits: Document[];
  found: number;
}

export interface SpeechRemark {
  topic: string;
  details: string[];
  video_urls: string[];
}

export interface LegislatorRemark {
  name: string;
  party: string;
  area: string;
  avatar: string;
  remarks: SpeechRemark[];
}

export interface Topic {
  title: string;
  tags: string[];
  summary: string;
}
