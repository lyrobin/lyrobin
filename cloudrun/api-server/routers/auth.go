package routers

import (
	"strings"

	firebase "firebase.google.com/go/v4"
	"firebase.google.com/go/v4/auth"
	"github.com/gin-gonic/gin"
)

const (
	headerAuth       = "Authorization"
	headerXAuth      = "X-Forwarded-Authorization"
	keyFirebaseToken = "firebase-token"
)

func GetAuthBearer(ctx *gin.Context) string {
	auth := ctx.GetHeader(headerXAuth)
	if auth == "" {
		auth = ctx.GetHeader(headerAuth)
	}
	tokens := strings.Split(auth, " ")
	if len(tokens) != 2 {
		return ""
	}
	return tokens[1]
}

func FirebaseTokenFrom(ctx *gin.Context) *auth.Token {
	token, ok := ctx.Get(keyFirebaseToken)
	if !ok {
		return nil
	}
	return token.(*auth.Token)
}

func FirebaseAuth(app *firebase.App) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		auth, err := app.Auth(ctx.Request.Context())
		if err != nil {
			ctx.AbortWithError(500, err)
			return
		}
		idToken := GetAuthBearer(ctx)
		if idToken == "" {
			ctx.AbortWithStatus(401)
			return
		}
		token, err := auth.VerifyIDToken(ctx.Request.Context(), idToken)
		if err != nil {
			ctx.AbortWithError(401, err)
			return
		}
		ctx.Set(keyFirebaseToken, token)
		ctx.Next()
	}
}
