package models

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strings"
	"time"

	"cloud.google.com/go/firestore"
	firebase "firebase.google.com/go/v4"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/config"
	"google.golang.org/api/iterator"
)

type StoreReader interface {
	GetDocument(ctx context.Context, path string) (Document, error)
	GetMeeting(ctx context.Context, path string) (Meeting, error)
	GetMeetingFile(ctx context.Context, path string) (MeetingFile, error)
	GetAttachment(ctx context.Context, path string) (Attachment, error)
	GetProceeding(ctx context.Context, path string) (Proceeding, error)
	GetVideo(ctx context.Context, path string) (Video, error)
	GetLegislator(ctx context.Context, path string) (Legislator, error)
	GetTopicByTags(ctx context.Context, tags []string) (Topic, error)
	ListNewsReports(ctx context.Context, startAt string, limit int) ([]NewsReport, error)
}

type Document struct {
	Summary string `firestore:"ai_summary,omitempty"`
}

type Meeting struct {
	ID      string `firestore:"meeting_no,omitempty"`
	Name    string `firestore:"meeting_name,omitempty"`
	Content string `firestore:"meeting_content,omitempty"`
	Summary string `firestore:"ai_summary,omitempty"`
	DateDes string `firestore:"meeting_date_desc,omitempty"`
}

type MeetingFile struct {
	Name     string   `firestore:"name,omitempty"`
	URL      string   `firestore:"url,omitempty"`
	Content  string   `firestore:"full_text,omitempty"`
	Summary  string   `firestore:"ai_summary,omitempty"`
	HashTags []string `firestore:"hash_tags,omitempty"`
}

type Attachment struct {
	Name     string   `firestore:"name,omitempty"`
	URL      string   `firestore:"url,omitempty"`
	Content  string   `firestore:"full_text,omitempty"`
	Summary  string   `firestore:"ai_summary,omitempty"`
	HashTags []string `firestore:"hash_tags,omitempty"`
}

type Proceeding struct {
	Name      string   `firestore:"name,omitempty"`
	URL       string   `firestore:"url,omitempty"`
	Summary   string   `firestore:"ai_summary,omitempty"`
	Status    string   `firestore:"status,omitempty"`
	Proposers []string `firestore:"proposers,omitempty"`
	Sponsors  []string `firestore:"sponsors,omitempty"`
}

type Video struct {
	URL        string    `firestore:"url,omitempty"`
	Summary    string    `firestore:"ai_summary,omitempty"`
	Transcript string    `firestore:"transcript,omitempty"`
	Member     string    `firestore:"member,omitempty"`
	Clips      []string  `firestore:"clips,omitempty"`
	Playlist   string    `firestore:"playlist,omitempty"`
	HdPlaylist string    `firestore:"hd_playlist,omitempty"`
	HashTags   []string  `firestore:"hash_tags,omitempty"`
	StartTime  time.Time `firestore:"start_time,omitempty"`
}

type Legislator struct {
	Name    string `firestore:"name,omitempty"`
	Party   string `firestore:"party,omitempty"`
	Area    string `firestore:"area,omitempty"`
	Avatar  string `firestore:"avatar,omitempty"`
	Remarks string `firestore:"ai_summary,omitempty"`
}

type Topic struct {
	Title   string   `firestore:"title,omitempty" json:"title,omitempty"`
	Summary string   `firestore:"summary,omitempty" json:"summary,omitempty"`
	Tags    []string `firestore:"tags,omitempty" json:"tags,omitempty"`
}

type NewsReport struct {
	Title         string    `firestore:"title,omitempty" json:"title,omitempty"`
	SourceURI     string    `firestore:"source_uri,omitempty" json:"source_uri,omitempty"`
	TranscriptURI string    `firestore:"transcript_uri,omitempty" json:"transcript_uri,omitempty"`
	Content       string    `firestore:"content,omitempty" json:"content,omitempty"`
	Keywords      []string  `firestore:"keywords,omitempty" json:"keywords,omitempty"`
	Legislators   []string  `firestore:"legislators,omitempty" json:"legislators,omitempty"`
	ReportDate    time.Time `firestore:"report_date,omitempty" json:"report_date,omitempty"`
	ID            string    `json:"id,omitempty"`
}

var _ StoreReader = &FireStore{}

type FireStore struct {
	App *firebase.App
}

func (s *FireStore) GetMeeting(ctx context.Context, path string) (Meeting, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return Meeting{}, err
	}
	defer client.Close()
	doc, err := client.Doc(path).Get(ctx)
	if err != nil || !doc.Exists() {
		return Meeting{}, errors.New(path + " not found")
	}
	var meeting Meeting
	doc.DataTo(&meeting)
	return meeting, nil
}

func (s *FireStore) GetMeetingFile(ctx context.Context, path string) (MeetingFile, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return MeetingFile{}, err
	}
	defer client.Close()
	doc, err := client.Doc(path).Get(ctx)
	if err != nil || !doc.Exists() {
		return MeetingFile{}, errors.New(path + " not found")
	}
	var meetingFile MeetingFile
	doc.DataTo(&meetingFile)
	return meetingFile, nil
}

func (s *FireStore) GetAttachment(ctx context.Context, path string) (Attachment, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return Attachment{}, err
	}
	defer client.Close()
	doc, err := client.Doc(path).Get(ctx)
	if err != nil || !doc.Exists() {
		return Attachment{}, errors.New(path + " not found")
	}
	var attachment Attachment
	doc.DataTo(&attachment)
	return attachment, nil
}

func (s *FireStore) GetProceeding(ctx context.Context, path string) (Proceeding, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return Proceeding{}, err
	}
	defer client.Close()
	doc, err := client.Doc(path).Get(ctx)
	if err != nil || !doc.Exists() {
		return Proceeding{}, errors.New(path + " not found")
	}
	var proceeding Proceeding
	if err := doc.DataTo(&proceeding); err != nil {
		return Proceeding{}, err
	}
	return proceeding, nil
}

func (s *FireStore) GetVideo(ctx context.Context, path string) (Video, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return Video{}, err
	}
	defer client.Close()
	doc, err := client.Doc(path).Get(ctx)
	if err != nil || !doc.Exists() {
		return Video{}, errors.New(path + " not found")
	}
	var video Video
	if err := doc.DataTo(&video); err != nil {
		return Video{}, err
	}
	return video, nil
}

func (s *FireStore) GetLegislator(ctx context.Context, path string) (Legislator, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return Legislator{}, err
	}
	defer client.Close()
	doc, err := client.Doc(path).Get(ctx)
	if err != nil || !doc.Exists() {
		return Legislator{}, errors.New(path + " not found")
	}
	var legislator Legislator
	if err := doc.DataTo(&legislator); err != nil {
		return Legislator{}, err
	}
	return legislator, nil
}

func (m Meeting) GetURL() string {
	cfg, err := config.Environ()
	if err != nil {
		return ""
	}
	tokens := strings.SplitN(m.DateDes, " ", 2)
	if len(tokens) < 2 {
		return ""
	}
	path, err := url.JoinPath(cfg.Legislative.Domain, "ppg/sittings", m.ID, "details")
	if err != nil {
		return ""
	}
	meetingURL, err := url.Parse(path)
	if err != nil {
		return ""
	}
	meetingURL.RawQuery = fmt.Sprintf("meetingDate=%s", tokens[0])
	return meetingURL.String()
}

func (s *FireStore) GetDocument(ctx context.Context, path string) (Document, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return Document{}, nil
	}
	defer client.Close()
	doc, err := client.Doc(path).Get(ctx)
	if err != nil || !doc.Exists() {
		return Document{}, errors.New(path + " not found")
	}
	var document Document
	doc.DataTo(&document)
	return document, nil
}

func (s *FireStore) GetTopicByTags(ctx context.Context, tags []string) (Topic, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return Topic{}, err
	}
	defer client.Close()

	iter := client.Collection(
		"topics",
	).Where(
		"tags", "array-contains-any", tags,
	).Where(
		"summarized", "==", true,
	).OrderBy(
		"timestamp", firestore.Desc,
	).Limit(1).Documents(ctx)

	var topics []Topic
	for {
		doc, err := iter.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return Topic{}, err
		}
		var topic Topic
		doc.DataTo(&topic)
		topics = append(topics, topic)
	}
	if len(topics) <= 0 {
		return Topic{}, errors.New("topic not found")
	}
	return topics[0], nil
}

func (s *FireStore) ListNewsReports(ctx context.Context, startAfter string, limit int) ([]NewsReport, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return nil, err
	}
	defer client.Close()

	query := client.Collection(
		"news_reports",
	).Where(
		"is_ready", "==", true,
	).OrderBy(
		"report_date", firestore.Desc,
	)

	if startAfter != "" {
		if !strings.HasPrefix(startAfter, "news_reports/") {
			startAfter = "news_reports/" + startAfter
		}
		doc, err := client.Doc(startAfter).Get(ctx)
		if err != nil {
			return nil, err
		}
		query = query.StartAfter(doc)
	}

	iter := query.Limit(
		limit,
	).Documents(ctx)

	reports := []NewsReport{}
	for {
		doc, err := iter.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return nil, err
		}
		var report NewsReport
		doc.DataTo(&report)
		report.ID = strings.TrimPrefix(doc.Ref.Path, doc.Ref.Parent.Path+"/")
		reports = append(reports, report)
	}
	return reports, nil
}
