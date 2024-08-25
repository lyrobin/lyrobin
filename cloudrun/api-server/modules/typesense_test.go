package modules_test

import (
	"context"
	"log"
	"testing"

	firebase "firebase.google.com/go/v4"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/config"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/modules"
)

func getTypesenseEngine(ctx context.Context, t *testing.T) modules.SearchEngine {
	cfg, err := config.Environ()
	if err != nil {
		log.Fatal(err)
	}
	app, err := firebase.NewApp(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	store := &models.FireStore{
		App: app,
	}
	return modules.NewTypesenseEngine(cfg.TypeSense, store)
}

func TestSearchLegislator(t *testing.T) {
	ctx := context.Background()
	se := getTypesenseEngine(ctx, t)
	_, err := se.SearchLegislator(ctx, "葛如鈞")
	if err != nil {
		t.Error(err)
	}
}

func TestSearch(t *testing.T) {
	ctx := context.Background()

	se := getTypesenseEngine(ctx, t)

	t.Run("Search Hashtags", func(t *testing.T) {
		rst, err := se.Search(ctx, modules.SearchRequest{
			Query: "#打詐 沈發惠",
		})
		if err != nil {
			t.Error(err)
		}
		if rst.Found <= 0 {
			t.Error("No result")
		}
		paths := make(map[string]struct{})
		for _, hit := range rst.Hits {
			paths[hit.Path] = struct{}{}
		}
		expect := "meetings/2024062890/ivods/00157616358118550769/speeches/584ad74f033c3d41a0a32e0280ec7c60"
		_, ok := paths[expect]
		if !ok {
			t.Error("Expect ", expect, ", got: ", paths)
		}
	})

	t.Run("Search multiple hashtags", func(t *testing.T) {
		rst, err := se.Search(ctx, modules.SearchRequest{
			Query: "#打詐 #臉書",
		})
		if err != nil {
			t.Error(err)
		}
		paths := make(map[string]modules.Document)
		for _, hit := range rst.Hits {
			paths[hit.Path] = hit
		}
		expect := "meetings/2024041987/ivods/00572664474935437062/speeches/be8c0e797ba93be785dbe68fb316d4bc"
		doc, ok := paths[expect]
		if !ok {
			t.Error("Expect ", expect, ", got: ", paths)
		}
		hashtags := make(map[string]struct{})
		for _, tag := range doc.HashTags {
			hashtags[tag] = struct{}{}
		}
		if _, ok := hashtags["打詐"]; !ok {
			t.Error("Expect #打詐 in ", hashtags)
		}
		if _, ok := hashtags["臉書"]; !ok {
			t.Error("Expect #臉書 in ", hashtags)
		}
	})
}
