package routers

import (
	"fmt"
	"strconv"

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

func HandleGetVideoPlaylist(store models.StoreReader) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		meet := ctx.Param("meetID")
		ivod := ctx.Param("ivodID")
		collection := ctx.Param("collection")
		video := ctx.Param("videoID")

		if collection != "videos" && collection != "speeches" {
			ctx.String(404, "collection %s not found", collection)
			return
		}
		docPath := fmt.Sprintf("meetings/%s/ivods/%s/%s/%s", meet, ivod, collection, video)
		v, err := store.GetVideo(ctx.Request.Context(), docPath)
		if err != nil {
			ctx.String(404, err.Error())
			return
		}
		if v.HdPlaylist != "" {
			ctx.String(200, v.HdPlaylist)
			return
		}
		if v.Playlist != "" {
			ctx.String(200, v.Playlist)
			return
		}
		ctx.String(404, "playlist not found")
	}
}

func HandleListNewsReports(store models.StoreReader) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		startAfter := ctx.Query("start")
		limit := 10
		if q, ok := ctx.GetQuery("limit"); ok {
			limit, _ = strconv.Atoi(q)
		}
		if limit <= 0 {
			limit = 10
		}
		reports, err := store.ListNewsReports(ctx.Request.Context(), startAfter, limit)
		if err != nil {
			ctx.String(404, err.Error())
			return
		}
		ctx.JSON(200, reports)
	}
}

func HandleGetSpeechTranscript(store models.StoreReader) gin.HandlerFunc {
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
		ctx.String(200, v.Transcript)
	}
}
