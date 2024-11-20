package main

import (
	"context"
	"encoding/json"
	"flag"
	"log"
	"sort"
	"time"

	"cloud.google.com/go/firestore"
	firebase "firebase.google.com/go/v4"
	"github.com/apache/beam/sdks/v2/go/pkg/beam"
	"github.com/apache/beam/sdks/v2/go/pkg/beam/register"
	"github.com/apache/beam/sdks/v2/go/pkg/beam/x/beamx"
	"google.golang.org/api/iterator"
)

const minimumCount = 50
const maxCount = 150

type hashtagCount struct {
	Hashtag string
	Count   int64
}

type HashtagAccumulator struct {
	Tags map[string]int
}

type HashtagsSlice struct {
	Hashtags []string
}

func init() {
	register.Function2x0(listCollectionGroups)
	register.DoFn3x1(&getHashtagsFn{})
	register.Function2x0(hashTagCountMapFn)
	register.Function2x1(hashTagCountReduceFn)
	register.Function3x0(filterHashTagCountFn)
	register.Combiner3[HashtagAccumulator, hashtagCount, HashtagsSlice](&mergeTagsFn{})
	register.Function1x1(formatFn)
	register.DoFn3x1(&teardownFn{})
}

func listCollectionGroups(_ []byte, emit func(x string)) {
	for _, g := range []string{"files", "speeches", "attachments"} {
		emit(g)
	}
}

type getHashtagsFn struct {
	client *firestore.Client
}

func (fn *getHashtagsFn) StartBundle(ctx context.Context, emit func(string)) error {
	app, err := firebase.NewApp(ctx, nil)
	if err != nil {
		return err
	}
	fn.client, err = app.Firestore(ctx)
	return err
}

func (fn *getHashtagsFn) FinishBundle(ctx context.Context, emit func(string)) error {
	if err := fn.client.Close(); err != nil {
		return err
	}
	return nil
}

func (fn *getHashtagsFn) ProcessElement(ctx context.Context, group string, emit func(string)) error {
	log.Println("Processing hashtags")
	postMonth := time.Now().AddDate(0, -6, 0)

	iter := fn.client.CollectionGroup(group).Where("hash_tags_summarized_at", ">=", postMonth).Documents(ctx)
	for {
		doc, err := iter.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return err
		}
		v, ok := doc.Data()["hash_tags"]
		if !ok {
			continue
		}
		for _, tag := range v.([]interface{}) {
			emit(tag.(string))
			log.Printf("Hashtag: %s\n", tag)
		}
	}
	return nil
}

func hashTagCountMapFn(tag string, emit func(x string, y int64)) {
	emit(tag, 1)
}

func hashTagCountReduceFn(a, b int64) int64 {
	return a + b
}

func filterHashTagCountFn(tag string, count int64, emit func(hashtagCount)) {
	if count >= minimumCount && count <= maxCount {
		emit(hashtagCount{Hashtag: tag, Count: count})
	}
}

type mergeTagsFn struct{}

func (fn *mergeTagsFn) CreateAccumulator() HashtagAccumulator {
	return HashtagAccumulator{Tags: make(map[string]int)}
}

func (fn *mergeTagsFn) AddInput(tags HashtagAccumulator, tag hashtagCount) HashtagAccumulator {
	tags.Tags[tag.Hashtag] += int(tag.Count)
	return tags
}

func (fn *mergeTagsFn) MergeAccumulators(a, b HashtagAccumulator) HashtagAccumulator {
	for k, v := range b.Tags {
		a.Tags[k] += v
	}
	return a
}

func (fn *mergeTagsFn) ExtractOutput(acc HashtagAccumulator) HashtagsSlice {
	// sort tags by count
	type tagCount struct {
		Tag   string
		Count int
	}

	var tagCounts []tagCount
	for tag, count := range acc.Tags {
		tagCounts = append(tagCounts, tagCount{Tag: tag, Count: count})
	}

	sort.Slice(tagCounts, func(i, j int) bool {
		return tagCounts[i].Count > tagCounts[j].Count
	})

	var sortedTags []string
	for _, tc := range tagCounts {
		log.Printf("Tag: %s, Count: %d\n", tc.Tag, tc.Count)
		sortedTags = append(sortedTags, tc.Tag)
	}

	return HashtagsSlice{Hashtags: sortedTags[10:]}
}

func (fn *mergeTagsFn) Compact(tags map[string]int) map[string]int {
	return tags
}

func formatFn(tags HashtagsSlice) string {
	o, _ := json.Marshal(tags.Hashtags)
	return string(o)
}

type teardownFn struct{}

func (fn *teardownFn) ProcessElement(ctx context.Context, _ int, fetch func(*string) bool) error {
	var txt string
	app, err := firebase.NewApp(ctx, nil)
	if err != nil {
		return err
	}
	client, err := app.Firestore(ctx)
	if err != nil {
		return err
	}
	defer client.Close()
	for fetch(&txt) {
		var tags []string
		if err := json.Unmarshal([]byte(txt), &tags); err != nil {
			return err
		}
		doc := client.Collection("hot_keywords").Doc(time.Now().Format("2006-01-02"))
		_, err = doc.Set(ctx, map[string]interface{}{
			"keywords":  tags,
			"timestamp": firestore.ServerTimestamp,
		})
		if err != nil {
			return err
		}
	}
	return nil
}

func Teardown(s beam.Scope, col beam.PCollection) {
	pre := beam.AddFixedKey(s, col)
	post := beam.GroupByKey(s, pre)
	beam.ParDo0(s, &teardownFn{}, post)
}
func main() {
	flag.Parse()
	beam.Init()

	p, s := beam.NewPipelineWithRoot()
	impulse := beam.Impulse(s)
	groups := beam.ParDo(s, listCollectionGroups, impulse)
	hashtag := beam.ParDo(s, &getHashtagsFn{}, groups)
	counted := beam.ParDo(s, hashTagCountMapFn, hashtag)
	summed := beam.CombinePerKey(s, hashTagCountReduceFn, counted)
	filtered := beam.ParDo(s, filterHashTagCountFn, summed)
	merged := beam.Combine(s, &mergeTagsFn{}, filtered)
	formatted := beam.ParDo(s, formatFn, merged)
	Teardown(s, formatted)

	ctx := context.Background()
	if err := beamx.Run(ctx, p); err != nil {
		log.Fatal(err)
	}
}
