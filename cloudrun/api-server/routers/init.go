package routers

import (
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/modules"
	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
)

type Router struct {
	modules.SearchEngine
	models.StoreReader
}

func (r Router) Register(e *gin.Engine) {
	e.Use(cors.Default())
	e.GET("/search", HandleSearch(r.SearchEngine))
	{
		g := e.Group("/ai")
		g.GET("/summary", HandleAISummary(r.StoreReader))
	}
}
