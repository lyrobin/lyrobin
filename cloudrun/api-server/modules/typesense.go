// Package modules define modules.
package modules

import (
	"context"
	"errors"
	"fmt"
	"strings"
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
	Video       DocType = "video"
	Member      DocType = "legislator"
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
	Path        string      `json:"path,omitempty"`
	Name        string      `json:"name,omitempty"`
	Content     string      `json:"content,omitempty"`
	URL         string      `json:"url,omitempty"`
	DocType     string      `json:"doctype,omitempty"`
	CreatedDate int64       `json:"created_date,omitempty"`
	HashTags    []string    `json:"hashtags,omitempty"`
	Meta        interface{} `json:"meta,omitempty"`
}

type AttachmentMeta struct {
	Artifacts map[string]string `json:"artifacts,omitempty"`
}

type MeetingFileMeta struct {
	Artifacts map[string]string `json:"artifacts,omitempty"`
}

// DocumentHit is a simplified version of Document
type DocumentHit struct {
	Path    string `json:"path,omitempty"`
	DocType string `json:"doc_type,omitempty"`
}

type SpeechRemark struct {
	Topic     string    `json:"topic,omitempty"`
	Details   []string  `json:"details,omitempty"`
	Video     []string  `json:"video_urls,omitempty"`
	CreatedAt time.Time `json:"created_at,omitempty"`
}

type Legislator struct {
	Name    string         `json:"name,omitempty"`
	Party   string         `json:"party,omitempty"`
	Area    string         `json:"area,omitempty"`
	Avatar  string         `json:"avatar,omitempty"`
	Remarks []SpeechRemark `json:"remarks,omitempty"`
}

type SearchEngine interface {
	Search(ctx context.Context, req SearchRequest) (SearchResult, error)
	SearchDocumentHits(ctx context.Context, req SearchRequest) ([]DocumentHit, error)
	SearchLegislator(ctx context.Context, name string) (Legislator, error)
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

func (e typesenseEngine) search(ctx context.Context, req SearchRequest) (*api.SearchResult, error) {
	filter := "doc_type:!legislator"
	if req.Filter != "" {
		filter += "&&" + req.Filter
	}
	query, hashtags := req.SplitHashtags()
	if query == "" {
		query = "*"
	}
	if len(hashtags) > 0 {
		for i, h := range hashtags {
			hashtags[i] = fmt.Sprintf("hashtags:=%s", h)
		}
		filter += "&&" + strings.Join(hashtags, "&&")
	}
	params := &api.SearchCollectionParams{
		Q:                       req.Query,
		QueryBy:                 "name,content,summary,*",
		FacetBy:                 pointer.String("*"),
		FilterBy:                pointer.String(filter),
		ExcludeFields:           pointer.String("vector"),
		HighlightFields:         pointer.String("name,content,summary,transcript"),
		SnippetThreshold:        pointer.Int(200),
		HighlightAffixNumTokens: pointer.Int(60),
		PerPage:                 pointer.Int(20),
		Page:                    pointer.Int((req.Page)),
	}
	return e.client.Collection(collection).Documents().Search(ctx, params)
}

func (e typesenseEngine) SearchDocumentHits(ctx context.Context, req SearchRequest) ([]DocumentHit, error) {
	results, err := e.search(ctx, req)
	if err != nil {
		return nil, err
	}
	var hits []DocumentHit
	for _, h := range *results.Hits {
		hit, err := e.convertHitToDocumentHit(h)
		if err != nil {
			return nil, err
		}
		hits = append(hits, hit)
	}
	return hits, nil
}

func (e typesenseEngine) fetchFacets(result *api.SearchResult) []Facet {
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
	return facets
}

func (e typesenseEngine) Search(ctx context.Context, req SearchRequest) (SearchResult, error) {
	result, err := e.search(ctx, req)
	if err != nil {
		return SearchResult{}, err
	}
	facets := e.fetchFacets(result)
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

func (e typesenseEngine) SearchLegislator(ctx context.Context, name string) (Legislator, error) {
	if len([]rune(name)) < 2 {
		return Legislator{}, errors.New("name too short")
	}
	params := &api.SearchCollectionParams{
		Q:                   "*",
		QueryBy:             "name",
		FilterBy:            pointer.String("doc_type:=legislator && name:" + name),
		ExcludeFields:       pointer.String("vector"),
		PerPage:             pointer.Int(1),
		Page:                pointer.Int(1),
		SplitJoinTokens:     pointer.String("off"),
		NumTypos:            pointer.String("0"),
		TypoTokensThreshold: pointer.Int(0),
	}
	result, err := e.client.Collection(collection).Documents().Search(ctx, params)
	if err != nil {
		return Legislator{}, err
	}
	if len(*result.Hits) <= 0 {
		return Legislator{}, errors.New("not found")
	}
	h := (*result.Hits)[0]
	doc := *h.Document
	path, ok := doc["path"].(string)
	if !ok {
		return Legislator{}, errors.New("can't find `path` in hit")
	}
	legislator, err := e.store.GetLegislator(ctx, path)
	if err != nil {
		return Legislator{}, err
	}
	response := Legislator{
		Name:    legislator.Name,
		Party:   legislator.Party,
		Area:    legislator.Area,
		Avatar:  legislator.Avatar,
		Remarks: []SpeechRemark{},
	}
	topics, err := e.store.FindLegislatorSpeechesTopics(ctx, path)
	var remarks []SpeechRemark
	if err != nil {
		return response, nil
	}
	for _, t := range topics {
		remarks = append(remarks, SpeechRemark{
			Topic:     t.Title,
			Details:   t.Remarks,
			Video:     t.Videos,
			CreatedAt: t.CreatedAt,
		})
	}
	response.Remarks = remarks
	return response, nil
}

func (e typesenseEngine) convertHitToDocumentHit(h api.SearchResultHit) (DocumentHit, error) {
	doc := *h.Document
	docType, ok := doc["doc_type"].(string)
	if !ok {
		return DocumentHit{}, errors.New("can't find `doc_type` in hit")
	}
	path, ok := doc["path"].(string)
	if !ok {
		return DocumentHit{}, errors.New("can't find `path` in hit")
	}
	return DocumentHit{
		Path:    path,
		DocType: docType,
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
	createdDateFloat, _ := doc["created_date"].(float64)
	createdDate := int64(createdDateFloat)
	highlights := Highlights(*h.Highlights)
	switch DocType(docType) {
	case Meeting:
		m, err := e.store.GetMeeting(ctx, path)
		if err != nil {
			return Document{}, err
		}
		return Document{
			Name:        highlights.getSnippet("name", m.Name),
			Path:        path,
			Content:     highlights.getSnippet("content", trimString(m.Content, 500)),
			URL:         m.GetURL(),
			DocType:     docType,
			CreatedDate: createdDate,
		}, nil
	case MeetingFile:
		m, err := e.store.GetMeetingFile(ctx, path)
		if err != nil {
			return Document{}, err
		}
		meeting, err := e.store.GetMeeting(ctx, path)
		if err != nil {
			return Document{}, err
		}
		return Document{
			Name:        fmt.Sprintf("%s - %s", meeting.Name, m.Name),
			Path:        path,
			Content:     highlights.getSnippet("content", trimString(m.Content, 500)),
			URL:         meeting.GetURL(),
			DocType:     docType,
			CreatedDate: createdDate,
			HashTags:    m.HashTags,
			Meta:        MeetingFileMeta{Artifacts: map[string]string{m.Name: m.URL}},
		}, nil
	case Attachment:
		m, err := e.store.GetAttachment(ctx, path)
		if err != nil {
			return Document{}, err
		}
		proceeding, err := e.store.GetProceeding(ctx, path)
		if err != nil {
			return Document{}, err
		}
		return Document{
			Name:        proceeding.Name,
			Path:        path,
			Content:     highlights.getSnippet("content", trimString(m.Content, 500)),
			URL:         proceeding.URL,
			DocType:     docType,
			CreatedDate: createdDate,
			HashTags:    m.HashTags,
			Meta:        AttachmentMeta{Artifacts: map[string]string{m.Name: m.URL}},
		}, nil
	case Proceeding:
		m, err := e.store.GetProceeding(ctx, path)
		if err != nil {
			return Document{}, err
		}
		return Document{
			Name:        highlights.getSnippet("name", m.Name),
			Path:        path,
			Content:     highlights.getSnippet("content", trimString(m.Status, 200)),
			URL:         m.URL,
			DocType:     docType,
			CreatedDate: createdDate,
		}, nil
	case Video:
		meetPath := strings.Join(strings.Split(path, "/")[0:2], "/")
		meet, err := e.store.GetMeeting(ctx, meetPath)
		if err != nil {
			return Document{}, err
		}
		m, err := e.store.GetVideo(ctx, path)
		if err != nil {
			return Document{}, err
		}
		content := highlights.getSnippet("transcript", trimString(m.Transcript, 200))
		if content == "" {
			content = trimString(m.Summary, 30)
		}
		return Document{
			Name:        meet.Name + " - " + m.Member,
			Path:        path,
			Content:     content,
			URL:         m.URL,
			DocType:     docType,
			CreatedDate: createdDate,
			HashTags:    m.HashTags,
		}, nil
	default:
		return Document{}, errors.New("invalid document type " + docType)
	}
}

type Highlights []api.SearchHighlight

func (h Highlights) getSnippet(field string, d string) string {
	for _, f := range h {
		if *f.Field == field {
			return *f.Snippet + "…"
		}
	}
	return d
}

func trimString(s string, max int) string {
	runes := []rune(s)
	if len(runes) <= max {
		return s
	}
	return string(runes[:max]) + "…"
}

func (r SearchRequest) SplitHashtags() (string, []string) {
	var hashtags []string
	var queries []string
	for _, q := range strings.Split(r.Query, " ") {
		q = strings.TrimSpace(q)
		if strings.HasPrefix(q, "#") {
			hashtags = append(hashtags, q[1:])
		} else {
			queries = append(queries, q)
		}
	}
	return strings.Join(queries, " "), hashtags
}
