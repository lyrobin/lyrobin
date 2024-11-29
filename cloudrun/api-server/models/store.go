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
	FindLegislatorSpeechesTopics(ctx context.Context, path string) ([]SpeechTopic, error)
	GetTopicByTags(ctx context.Context, tags []string) (Topic, error)
	ListNewsReports(ctx context.Context, startAt string, limit int) ([]NewsReport, error)
	GetUser(ctx context.Context, uid string) (User, error)
	FindMeeting(ctx context.Context, path string) (Meeting, error)
	GetHotKeywords(ctx context.Context) ([]string, error)
}

type StoreWriter interface {
	UpdateUser(ctx context.Context, user User) error
}

type StoreReaderWriter interface {
	StoreReader
	StoreWriter
}

type Document struct {
	Summary string `firestore:"ai_summary,omitempty"`
}

type Meeting struct {
	ID      string `firestore:"meeting_no,omitempty"`
	Name    string `firestore:"meeting_name,omitempty"`
	Content string `firestore:"meeting_content,omitempty"`
	Summary string `firestore:"ai_summary,omitempty"`
	Unit    string `firestore:"meeting_unit,omitempty"`
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
	Name   string `firestore:"name,omitempty"`
	Party  string `firestore:"party,omitempty"`
	Area   string `firestore:"area,omitempty"`
	Avatar string `firestore:"avatar,omitempty"`
}

type SpeechTopic struct {
	Title     string    `firestore:"title,omitempty"`
	Remarks   []string  `firestore:"remarks,omitempty"`
	Videos    []string  `firestore:"videos,omitempty"`
	Ready     bool      `firestore:"ready,omitempty"`
	CreatedAt time.Time `firestore:"created_at,omitempty"`
}

type Topic struct {
	Title     string    `firestore:"title,omitempty" json:"title,omitempty"`
	Summary   string    `firestore:"summary,omitempty" json:"summary,omitempty"`
	Tags      []string  `firestore:"tags,omitempty" json:"tags,omitempty"`
	Timestamp time.Time `firestore:"timestamp,omitempty" json:"timestamp,omitempty"`
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

type User struct {
	ID           string    `firestore:"uid,omitempty"`
	AccessToken  string    `firestore:"google_access_token,omitempty"`
	RefreshToken string    `firestore:"google_refresh_token,omitempty"`
	Expiry       time.Time `firestore:"google_expiration_time,omitempty"`
	GeminiKey    string    `firestore:"gemini_key,omitempty"`
}

var _ StoreReader = &FireStore{}
var _ StoreWriter = &FireStore{}
var _ StoreReaderWriter = &FireStore{}

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
	if !strings.HasPrefix(path, "proceedings/") {
		return Proceeding{}, errors.New("invalid path: " + path)
	}
	parts := strings.Split(path, "/")
	if len(parts) < 2 {
		return Proceeding{}, errors.New("invalid path: " + path)
	}
	path = strings.Join(parts[:2], "/")
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
	doc, err := s.getLegislator(ctx, client, path)
	if err != nil {
		return Legislator{}, err
	}
	var legislator Legislator
	if err := doc.DataTo(&legislator); err != nil {
		return Legislator{}, err
	}
	return legislator, nil
}

func (s *FireStore) getLegislator(ctx context.Context, client *firestore.Client, path string) (*firestore.DocumentSnapshot, error) {
	doc, err := client.Doc(path).Get(ctx)
	if err != nil || !doc.Exists() {
		return nil, errors.New(path + " not found")
	}
	return doc, nil
}

func (s *FireStore) FindLegislatorSpeechesTopics(ctx context.Context, path string) ([]SpeechTopic, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return nil, err
	}
	defer client.Close()

	l, err := s.getLegislator(ctx, client, path)
	if err != nil {
		return nil, err
	}
	iter := l.Ref.Collection("summary").OrderBy("created_at", firestore.Desc).Limit(5).Documents(ctx)
	for {
		doc, err := iter.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return nil, err
		}
		topics, err := s.listLegislatorSummaryTopics(ctx, client, doc)
		if err != nil {
			continue
		}
		if len(topics) <= 0 {
			continue
		}
		ready := true
		for _, topic := range topics {
			if !topic.Ready {
				ready = false
				break
			}
		}
		if ready {
			return topics, nil
		}
	}
	return nil, errors.New("no ready topics found")
}

// listLegislatorSummaryTopics lists the topics of a legislator's speeches.
// the path is the path to the member's summary collection.
func (s *FireStore) listLegislatorSummaryTopics(ctx context.Context, client *firestore.Client, doc *firestore.DocumentSnapshot) ([]SpeechTopic, error) {
	iter := doc.Ref.Collection("topics").Documents(ctx)
	var result []SpeechTopic
	for {
		doc, err := iter.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return nil, err
		}
		var topic SpeechTopic
		doc.DataTo(&topic)
		result = append(result, topic)
	}
	return result, nil
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

func (s *FireStore) GetUser(ctx context.Context, uid string) (User, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return User{}, err
	}
	defer client.Close()
	doc, err := client.Collection("users").Doc(uid).Get(ctx)
	if err != nil || !doc.Exists() {
		return User{}, errors.New(uid + " not found")
	}
	var user User
	doc.DataTo(&user)
	return user, nil
}

func (s *FireStore) UpdateUser(ctx context.Context, user User) error {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return err
	}
	defer client.Close()
	doc := client.Collection("users").Doc(user.ID)
	_, err = doc.Update(
		ctx, []firestore.Update{
			{
				Path:  "gemini_key",
				Value: user.GeminiKey,
			},
		},
	)
	return err
}

func (s *FireStore) FindMeeting(ctx context.Context, path string) (Meeting, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return Meeting{}, err
	}
	defer client.Close()
	if !strings.HasPrefix(path, "meetings/") {
		return Meeting{}, fmt.Errorf("invalid path: %s", path)
	}
	parts := strings.Split(path, "/")
	if len(parts) < 2 {
		return Meeting{}, fmt.Errorf("invalid path: %s", path)
	}
	meetingPath := strings.Join(parts[:2], "/")
	return s.GetMeeting(ctx, meetingPath)
}

func (s *FireStore) GetHotKeywords(ctx context.Context) ([]string, error) {
	client, err := s.App.Firestore(ctx)
	if err != nil {
		return nil, err
	}
	defer client.Close()
	doc, err := client.Collection("hot_keywords").OrderBy("timestamp", firestore.Desc).Limit(1).Documents(ctx).Next()
	if err != nil || !doc.Exists() {
		return nil, errors.New("hot keywords not found")
	}
	var hotKeywords struct {
		Keywords []string `firestore:"keywords,omitempty"`
	}
	doc.DataTo(&hotKeywords)
	return hotKeywords.Keywords, nil
}
