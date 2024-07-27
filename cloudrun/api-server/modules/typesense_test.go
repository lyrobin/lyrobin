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

func TestSearchLegislator(t *testing.T) {
	ctx := context.Background()
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
	se := modules.NewTypesenseEngine(cfg.TypeSense, store)

	_, err = se.SearchLegislator(ctx, "葛如鈞")
	if err != nil {
		t.Error(err)
	}
}
