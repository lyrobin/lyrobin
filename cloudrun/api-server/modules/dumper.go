package modules

import (
	"context"
	"encoding/json"

	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
)

type ContextDumper struct {
	store models.StoreReader
}

func NewContextDumper(store models.StoreReader) *ContextDumper {
	return &ContextDumper{store: store}
}

func (d *ContextDumper) Dump(ctx context.Context, docs ...DocumentHit) string {
	if len(docs) == 0 {
		return ""
	}

	var results []map[string]string
	resultsCh := make(chan map[string]string, len(docs))
	errCh := make(chan error, len(docs))

	for _, doc := range docs {
		go func(doc DocumentHit) {
			m, ok := d.DumpDocumentAsMap(ctx, doc)
			if ok {
				resultsCh <- m
			} else {
				errCh <- nil
			}
		}(doc)
	}

	for range docs {
		select {
		case result := <-resultsCh:
			results = append(results, result)
		case <-errCh:
		}
	}

	if len(results) == 0 {
		return ""
	}
	out, err := json.MarshalIndent(results, "", "    ")
	if err != nil {
		return ""
	}
	return string(out)
}

func (d *ContextDumper) DumpDocumentAsMap(ctx context.Context, doc DocumentHit) (map[string]string, bool) {
	switch DocType(doc.DocType) {
	case Meeting:
		m, err := d.store.GetMeeting(ctx, doc.Path)
		if err != nil {
			return nil, false
		}
		return map[string]string{
			"會議名稱": m.Name,
			"會議日期": m.DateDes,
			"會議內容": m.Content,
			"委員會":  m.Unit,
		}, true
	case MeetingFile:
		m, err := d.store.GetMeetingFile(ctx, doc.Path)
		if err != nil {
			return nil, false
		}
		return map[string]string{
			"檔案名稱": m.Name,
			"摘要":   m.Summary,
		}, true
	case Attachment:
		m, err := d.store.GetAttachment(ctx, doc.Path)
		if err != nil {
			return nil, false
		}
		return map[string]string{
			"附件名稱": m.Name,
			"摘要":   m.Summary,
		}, true
	case Proceeding:
		m, err := d.store.GetProceeding(ctx, doc.Path)
		if err != nil {
			return nil, false
		}
		return map[string]string{
			"附件名稱": m.Name,
			"摘要":   m.Summary,
		}, true
	case Video:
		v, err := d.store.GetVideo(ctx, doc.Path)
		if err != nil {
			return nil, false
		}
		m, err := d.store.FindMeeting(ctx, doc.Path)
		if err != nil {
			return nil, false
		}
		return map[string]string{
			"發言者": v.Member,
			"逐字稿": v.Transcript,
			"委員會": m.Unit,
			"日期":  m.DateDes,
		}, true
	default:
		return nil, false
	}
}
