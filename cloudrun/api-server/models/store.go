package models

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strings"

	firebase "firebase.google.com/go/v4"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/config"
)

type StoreReader interface {
	GetDocument(ctx context.Context, path string) (Document, error)
	GetMeeting(ctx context.Context, path string) (Meeting, error)
	GetMeetingFile(ctx context.Context, path string) (MeetingFile, error)
	GetAttachment(ctx context.Context, path string) (Attachment, error)
	GetProceeding(ctx context.Context, path string) (Proceeding, error)
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
	Name    string `firestore:"name,omitempty"`
	URL     string `firestore:"url,omitempty"`
	Content string `firestore:"full_text,omitempty"`
	Summary string `firestore:"ai_summary,omitempty"`
}

type Attachment struct {
	Name    string `firestore:"name,omitempty"`
	URL     string `firestore:"url,omitempty"`
	Content string `firestore:"full_text,omitempty"`
	Summary string `firestore:"ai_summary,omitempty"`
}

type Proceeding struct {
	Name      string `firestore:"name,omitempty"`
	URL       string `firestore:"url,omitempty"`
	Summary   string `firestore:"ai_summary,omitempty"`
	Status    string `firestore:"status,omitempty"`
	Proposers string `firestore:"proposers,omitempty"`
	Sponsors  string `firestore:"sponsors,omitempty"`
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
	doc.DataTo(&proceeding)
	return proceeding, nil
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