package routers

import (
	"net/url"

	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/gin-gonic/gin"
)

func HandleAISummary(store models.StoreReader) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		p, ok := ctx.GetQuery("path")
		if !ok || p == "" {
			ctx.String(404, "path not found")
			return
		}
		p, err := url.QueryUnescape(p)
		if err != nil {
			ctx.String(400, "bad path")
			return
		}
		doc, err := store.GetDocument(ctx.Request.Context(), p)
		if err != nil {
			ctx.Status(500)
			return
		}
		ctx.String(200, doc.Summary)
	}
}
