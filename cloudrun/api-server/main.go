package main

import (
	"context"
	"fmt"
	"log"

	firebase "firebase.google.com/go/v4"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/config"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/modules"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/routers"
	"github.com/gin-gonic/gin"
)

func main() {
	ctx := context.Background()
	cfg, err := config.Environ()
	if err != nil {
		log.Fatal(err)
	}
	app, err := firebase.NewApp(ctx, nil)
	if err != nil {
		log.Fatal(err)
	}
	store := &models.FireStore{
		App: app,
	}
	se := modules.NewTypesenseEngine(cfg.TypeSense, store)
	router := routers.Router{
		SearchEngine:      se,
		StoreReaderWriter: store,
		App:               app,
	}
	r := gin.Default()
	router.Register(r)
	r.Run(fmt.Sprintf(":%s", cfg.Server.Port))
}
