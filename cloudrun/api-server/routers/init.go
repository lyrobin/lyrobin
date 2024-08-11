// Package routers define routes.
package routers

import (
	firebase "firebase.google.com/go/v4"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/modules"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/routers/docs"
	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	swaggerfiles "github.com/swaggo/files"
	ginSwagger "github.com/swaggo/gin-swagger"
)

//go:generate swag init --parseDependency --parseInternal -g ./init.go -d ./ -o ./docs

type Router struct {
	modules.SearchEngine
	models.StoreReader
	App *firebase.App
}

//	@title					lyrobin-legislative-search Legislative Search API
//	@version				1.0
//	@BasePath				/v1
//	@description			LY Robin's API to search legislative documents
//	@license.name			GPL-3.0
//	@license.url			https://www.gnu.org/licenses/gpl-3.0.html.en
//	@schemes				https
//	@produce				json
//	@x-google-backend		{"address": "https://api-server-dwuutdyikq-de.a.run.app"}
//	@x-google-management	{"metrics": [{"name": "read-requests", "displayName": "Read Requests", "valueType": "INT64", "metricKind": "DELTA"}], "quota": {"limits": [{"name": "read-requests-limit", "metric": "read-requests","unit": "1/min/{project}", "values": {"STANDARD": "1000"}}]}}

//	@securityDefinitions.apikey	ApiKeyHeader
//	@in							header
//	@name						x-api-key
//	@securityDefinitions.apikey	ApiKeyQuery
//	@in							query
//	@name						key

// Register routes
func (r Router) Register(e *gin.Engine) {
	corsConfig := cors.DefaultConfig()
	corsConfig.AllowCredentials = true
	corsConfig.AllowAllOrigins = true
	corsConfig.AllowHeaders = []string{"Origin", "Content-Length", "Content-Type", "Authorization", "X-Forwarded-Authorization"}
	e.Use(cors.New(corsConfig))
	e.GET("/search", HandleSearch(r.SearchEngine))
	{
		g := e.Group("/ai")
		g.GET("/summary", HandleAISummary(r.StoreReader))
		g.GET(("/legislator"), HandleSearchLegislator(r.SearchEngine))
	}
	{
		g := e.Group("/meetings/:meetID")
		g.Use(FirebaseAuth(r.App))
		{
			g := g.Group("/ivods/:ivodID")
			{
				g := g.Group("/speeches/:speechID")
				g.GET(("/video"), HandleGetSpeechVideo(r.StoreReader))
			}
			g.GET("/:collection/:videoID/playlist", HandleGetVideoPlaylist(r.StoreReader))
		}
	}

	// V1 APIs
	v1 := e.Group("/v1")
	v1.GET("/search", HandleSearch(r.SearchEngine))
	{
		g := v1.Group("/ai")
		g.GET("/summary", HandleAISummary(r.StoreReader))
		g.GET(("/legislator"), HandleSearchLegislator(r.SearchEngine))
	}

	docs.SwaggerInfo.BasePath = "/v1"
	v1.GET("/swagger", HandleSwaggerDoc)
	v1.GET("/swagger/*any", ginSwagger.WrapHandler(swaggerfiles.Handler))
}

// @ID				swagger-get
// @Tags			Swagger
// @Summary		Doc endpoint
// @Description	swagger document files
// @Param			file	path		string	true	"doc file"
// @Success		200		{object}	string
// @Router			/swagger/{file} [get]
func _() {}

// HandleSwaggerDoc request
//
//	@ID				api-doc
//	@Tags			Swagger
//	@Summary		Doc endpoint
//	@Description	swagger document
//	@Success		200	{string}	string
//	@Router			/swagger [get]
func HandleSwaggerDoc(ctx *gin.Context) {
	ctx.Redirect(301, "/v1/swagger/index.html")
}
