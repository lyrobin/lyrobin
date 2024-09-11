package models_test

import (
	"context"
	"testing"

	firebase "firebase.google.com/go/v4"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/google/go-cmp/cmp"
)

func TestGet(t *testing.T) {
	ctx := context.Background()
	app, err := firebase.NewApp(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	store := models.FireStore{App: app}

	t.Run("Meeting", func(t *testing.T) {
		m, err := store.GetMeeting(ctx, "meetings/2024013195")
		if err != nil {
			t.Error(err)
		}
		want := models.Meeting{
			ID:      "2024013195",
			Name:    "第11屆立法院預備會議",
			Content: "第11屆立法委員報到、就職宣誓暨院長、副院長選舉及就職宣誓",
			DateDes: "113/02/01 08:00-17:00",
		}
		if diff := cmp.Diff(m, want); diff != "" {
			t.Error(diff)
		}
		expect := "https://ppg.ly.gov.tw/ppg/sittings/2024013195/details?meetingDate=113/02/01"
		if diff := cmp.Diff(m.GetURL(), expect); diff != "" {
			t.Error(diff)
		}
	})
	t.Run("Proceeding", func(t *testing.T) {
		m, err := store.GetProceeding(ctx, "proceedings/202110010660000")
		if err != nil {
			t.Error(err)
		}
		if diff := cmp.Diff(m.Name, "本院委員伍麗華Saidhai Tahovecahe等16人擬具「海洋保育法草案」，請審議案。"); diff != "" {
			t.Error(diff)
		}
	})
}

func TestGetTopicByTags(t *testing.T) {
	ctx := context.Background()
	app, err := firebase.NewApp(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	store := models.FireStore{App: app}

	t.Run("Existing", func(t *testing.T) {
		topic, err := store.GetTopicByTags(ctx, []string{"健保"})
		if err != nil {
			t.Error(err)
		}
		if topic.Title == "" {
			t.Error("empty topic")
		}
	})
}
