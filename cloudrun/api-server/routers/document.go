package routers

import (
	"fmt"

	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/gin-gonic/gin"
)

func HandleGetSpeechVideo(store models.StoreReader) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		meet := ctx.Param("meetID")
		ivod := ctx.Param("ivodID")
		speech := ctx.Param("speechID")
		docPath := fmt.Sprintf("meetings/%s/ivods/%s/speeches/%s", meet, ivod, speech)
		v, err := store.GetVideo(ctx.Request.Context(), docPath)
		if err != nil {
			ctx.String(404, err.Error())
			return
		}
		if len(v.Clips) != 1 {
			ctx.String(404, "video not found")
			return
		}
		ctx.String(200, v.Clips[0])
	}
}
