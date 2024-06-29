package modules

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/config"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/rs/zerolog/log"
	"github.com/typesense/typesense-go/typesense"
	"github.com/typesense/typesense-go/typesense/api"
	"github.com/typesense/typesense-go/typesense/api/pointer"
)

const collection = "documents"

type DocType string

const (
	Meeting     DocType = "meeting"
	MeetingFile DocType = "meetingfile"
	Attachment  DocType = "attachment"
	Proceeding  DocType = "proceeding"
)

type SearchRequest struct {
	Query  string `json:"query"`
	Filter string `json:"filter"`
	Page   int    `json:"page"`
}

type FacetCount struct {
	Value string `json:"value,omitempty"`
	Count int    `json:"count,omitempty"`
}

type Facet struct {
	Field  string       `json:"field,omitempty"`
	Counts []FacetCount `json:"counts,omitempty"`
}

type SearchResult struct {
	Facet []Facet    `json:"facet,omitempty"`
	Hits  []Document `json:"hits,omitempty"`
	Found int        `json:"found,omitempty"`
}

type Document struct {
	Path    string `json:"path,omitempty"`
	Name    string `json:"name,omitempty"`
	Content string `json:"content,omitempty"`
	URL     string `json:"url,omitempty"`
}

type SearchEngine interface {
	Search(ctx context.Context, req SearchRequest) (SearchResult, error)
}

var _ SearchEngine = typesenseEngine{}

type typesenseEngine struct {
	store  models.StoreReader
	client *typesense.Client
}

func NewTypesenseEngine(cfg config.TypeSense, store models.StoreReader) SearchEngine {
	return typesenseEngine{
		store: store,
		client: typesense.NewClient(
			typesense.WithServer(fmt.Sprintf("%s://%s:%s", cfg.Protocol, cfg.Host, cfg.Port)),
			typesense.WithAPIKey(cfg.Key),
			typesense.WithConnectionTimeout(5*time.Second),
			typesense.WithCircuitBreakerMaxRequests(50),
			typesense.WithCircuitBreakerInterval(2*time.Minute),
			typesense.WithCircuitBreakerTimeout(1*time.Minute),
		),
	}
}

func (e typesenseEngine) Search(ctx context.Context, req SearchRequest) (SearchResult, error) {
	params := &api.SearchCollectionParams{
		Q:               req.Query,
		QueryBy:         "name,content,summary,*",
		FacetBy:         pointer.String("*"),
		FilterBy:        pointer.String(req.Filter),
		ExcludeFields:   pointer.String("vector"),
		HighlightFields: pointer.String("name,content,summary"),
		PerPage:         pointer.Int(20),
		Page:            pointer.Int((req.Page)),
	}
	result, err := e.client.Collection(collection).Documents().Search(ctx, params)
	if err != nil {
		return SearchResult{}, err
	}
	var facets []Facet
	for _, f := range *result.FacetCounts {
		var counts []FacetCount
		for _, c := range *f.Counts {
			counts = append(counts, FacetCount{
				Value: *c.Value,
				Count: *c.Count,
			})
		}
		facets = append(facets, Facet{
			Field:  *f.FieldName,
			Counts: counts,
		})
	}
	var hits []Document
	for _, h := range *result.Hits {
		doc, err := e.convertHitToDocument(ctx, h)
		if err != nil {
			log.Ctx(ctx).Warn().Err(err).Any("hit", h).Msg("can't convert hit to document")
		}
		hits = append(hits, doc)
	}
	return SearchResult{
		Facet: facets,
		Found: *result.Found,
		Hits:  hits,
	}, nil
}

func (e typesenseEngine) convertHitToDocument(ctx context.Context, h api.SearchResultHit) (Document, error) {
	doc := *h.Document
	docType, ok := doc["doc_type"].(string)
	if !ok {
		return Document{}, errors.New("can't find `doc_type` in hit")
	}
	path, ok := doc["path"].(string)
	if !ok {
		return Document{}, errors.New("can't find `path` in hit")
	}
	highlights := Highlights(*h.Highlights)
	switch DocType(docType) {
	case Meeting:
		m, err := e.store.GetMeeting(ctx, path)
		if err != nil {
			return Document{}, err
		}
		return Document{
			Name:    highlights.getSnippet("name", m.Name),
			Path:    path,
			Content: highlights.getSnippet("content", trimString(m.Content, 500)),
			URL:     m.GetURL(),
		}, nil
	case MeetingFile:
		m, err := e.store.GetMeetingFile(ctx, path)
		if err != nil {
			return Document{}, err
		}
		return Document{
			Name:    highlights.getSnippet("name", m.Name),
			Path:    path,
			Content: highlights.getSnippet("content", trimString(m.Content, 500)),
			URL:     m.URL,
		}, nil
	case Attachment:
		m, err := e.store.GetAttachment(ctx, path)
		if err != nil {
			return Document{}, err
		}
		return Document{
			Name:    highlights.getSnippet("name", m.Name),
			Path:    path,
			Content: highlights.getSnippet("content", trimString(m.Content, 500)),
			URL:     m.URL,
		}, nil
	default:
		return Document{}, errors.New("invalid document type " + docType)
	}
}

type Highlights []api.SearchHighlight

func (h Highlights) getSnippet(field string, d string) string {
	for _, f := range h {
		if *f.Field == field {
			return *f.Snippet
		}
	}
	return d
}

func trimString(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max] + "…"
}