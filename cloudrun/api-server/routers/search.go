package routers

import (
	"strconv"

	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/modules"
	"github.com/gin-gonic/gin"
)

func HandleSearch(se modules.SearchEngine) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		query, err := getSearchRequest(ctx)
		if err != nil {
			return
		}
		result, err := se.Search(ctx.Request.Context(), query)
		if err != nil {
			ctx.String(500, err.Error())
			return
		}
		ctx.JSON(200, result)
	}
}

func HandleSearchLegislator(se modules.SearchEngine) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		name, ok := ctx.GetQuery("name")
		if !ok {
			ctx.String(400, "name not found")
			return
		}
		result, err := se.SearchLegislator(ctx.Request.Context(), name)
		if err != nil {
			ctx.String(204, err.Error())
			return
		}
		ctx.JSON(200, result)

	}
}

func getSearchRequest(ctx *gin.Context) (modules.SearchRequest, error) {
	q, ok := ctx.GetQuery("q")
	if ok {
		var page int
		if p, err := strconv.ParseInt(ctx.Query("page"), 10, 32); err == nil {
			page = int(p)
		}
		return modules.SearchRequest{
			Query:  q,
			Filter: ctx.Query("filter"),
			Page:   page,
		}, nil
	}
	var query modules.SearchRequest
	err := ctx.BindJSON(&query)
	return query, err
}
