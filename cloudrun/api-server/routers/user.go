package routers

import (
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/gin-gonic/gin"
)

type UpdateUserGeminiKeyRequest struct {
	Key string `json:"key"`
}

func HandleUpdateUserGeminiKey(store models.StoreReaderWriter) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		token := FirebaseTokenFrom(ctx)
		if token == nil {
			ctx.AbortWithStatus(401)
			return
		}
		user, err := store.GetUser(ctx.Request.Context(), token.UID)
		if err != nil {
			ctx.AbortWithError(500, err)
			return
		}
		var req UpdateUserGeminiKeyRequest
		if err := ctx.BindJSON(&req); err != nil {
			ctx.AbortWithError(400, err)
			return
		}
		user.GeminiKey = req.Key
		if err := store.UpdateUser(ctx.Request.Context(), user); err != nil {
			ctx.AbortWithError(500, err)
			return
		}
		ctx.String(200, "ok")
	}
}

func HandleGetUserGeminiKey(store models.StoreReader) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		token := FirebaseTokenFrom(ctx)
		if token == nil {
			ctx.AbortWithStatus(401)
			return
		}
		user, err := store.GetUser(ctx.Request.Context(), token.UID)
		if err != nil {
			ctx.AbortWithError(500, err)
			return
		}
		ctx.String(200, user.GeminiKey)
	}
}
