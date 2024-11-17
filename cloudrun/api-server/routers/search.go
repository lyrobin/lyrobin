package routers

import (
	"math/rand/v2"
	"strconv"

	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/modules"
	"github.com/gin-gonic/gin"
)

// HandleSearch request
//
//	@ID				search-get
//	@Summary		Search documents
//	@Description	search any kind of documents, including videos.
//	@Tags			Search
//	@Param			q		query	string	false	"search query"
//	@Param			filter	query	string	false	"query filter"
//	@Param			page	query	int		false	"page to return"
//	@Security		ApiKeyHeader
//	@Security		ApiKeyQuery
//	@Success		200	{object}	modules.SearchResult
//	@Failure		500	{string}	string	"error"
//	@x-google-quota	{"metricCosts": {"read-requests": 1}}
//	@Router			/search [get]
func HandleSearch(se modules.SearchEngine) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		query, err := getSearchRequest(ctx)
		if err != nil {
			ctx.String(400, err.Error())
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

// HandleSearchLegislator requests
//
//	@ID				search-legislator-get
//	@Summary		Search legislator
//	@Description	search legislator's recent speeches and summary.
//	@Tags			AI
//	@Param			name	query	string	true	"legislator's name"
//	@Security		ApiKeyHeader
//	@Security		ApiKeyQuery
//	@Success		200	{object}	modules.Legislator
//	@Failure		400	{string}	string	"not found"
//	@x-google-quota	{"metricCosts": {"read-requests": 1}}
//	@Router			/ai/legislator [get]
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

func HandleSearchTopic(store models.StoreReader) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		tags, ok := ctx.GetQueryArray("tags")
		if !ok {
			ctx.String(400, "tags not found")
			return
		}
		topic, err := store.GetTopicByTags(ctx.Request.Context(), tags)
		if err != nil {
			ctx.String(204, err.Error())
			return
		}
		ctx.JSON(200, topic)
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

func HandleSearchFullContext(se modules.SearchEngine, store models.StoreReaderWriter) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		query, err := getSearchRequest(ctx)
		if err != nil {
			ctx.String(400, err.Error())
			return
		}
		limitQuery, ok := ctx.GetQuery("limit")
		limit := 5
		if ok {
			limit, err = strconv.Atoi(limitQuery)
			if err != nil {
				ctx.String(400, "bad limit")
				return
			}
		}

		var results []modules.DocumentHit
		for query.Page = 0; query.Page < limit; query.Page++ {
			hits, err := se.SearchDocumentHits(ctx.Request.Context(), query)
			if err != nil {
				ctx.String(500, err.Error())
				return
			}
			results = append(results, hits...)
		}
		dumper := modules.NewContextDumper(store)
		ctx.String(200, dumper.Dump(ctx.Request.Context(), results...))
	}
}

func HandleGetHotKeywords(store models.StoreReader) gin.HandlerFunc {
	return func(ctx *gin.Context) {
		keywords, err := store.GetHotKeywords(ctx.Request.Context())
		if err != nil {
			ctx.String(500, err.Error())
			return
		}
		var filteredKeywords []string
		for _, keyword := range keywords {

			if len([]rune(keyword)) <= 5 {
				filteredKeywords = append(filteredKeywords, keyword)
			}
		}
		rand.Shuffle(len(filteredKeywords), func(i, j int) {
			filteredKeywords[i], filteredKeywords[j] = filteredKeywords[j], filteredKeywords[i]
		})
		ctx.JSON(200, filteredKeywords[:5])
	}
}
