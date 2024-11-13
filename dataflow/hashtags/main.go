package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"log"
	"slices"
	"time"

	aiplatform "cloud.google.com/go/aiplatform/apiv1"
	"cloud.google.com/go/aiplatform/apiv1/aiplatformpb"
	"cloud.google.com/go/firestore"
	firebase "firebase.google.com/go/v4"
	"github.com/apache/beam/sdks/v2/go/pkg/beam"
	"github.com/apache/beam/sdks/v2/go/pkg/beam/register"
	"github.com/apache/beam/sdks/v2/go/pkg/beam/x/beamx"
	"github.com/blueworrybear/taiwan-legislative-search/cloudrun/api-server/models"
	"google.golang.org/api/idtoken"
	"google.golang.org/api/iterator"
	"google.golang.org/api/option"
	"google.golang.org/protobuf/types/known/structpb"
)

const (
	speechesCollection = "speeches"
	dimensionality     = 768
	distanceThreshold  = 0.85
	tagCountThreshold  = 5
	documentThreshold  = 10
	teardownTaskName   = "update_topics_summary"
)

func init() {
	register.DoFn3x1(&getHashtagsFn{})
	register.Function2x0(mapFn)
	register.Function2x1(combineFn)
	register.DoFn4x1(&mapHashTagCount{})
	register.Function1x1(formatFn)
	register.Combiner3[HashTagGroupAccumulator, HashtagCount, []HashTagGroup](&clusterFn{})
	register.Function2x0(flattenGroupsFn)
	register.DoFn3x1(&summaryHashTagsFn{})
	register.DoFn3x1(&teardownFn{})
}

type getHashtagsFn struct {
	client *firestore.Client
}

func (f *getHashtagsFn) StartBundle(ctx context.Context, emit func(string)) error {
	app, err := firebase.NewApp(ctx, nil)
	if err != nil {
		return err
	}
	f.client, err = app.Firestore(ctx)
	return err
}

func (f *getHashtagsFn) ProcessElement(ctx context.Context, _ []byte, emit func(string)) error {
	log.Println("Processing hashtags")
	pastThreeMonth := time.Now().AddDate(0, -3, 0)
	iter := f.client.CollectionGroup(speechesCollection).Where("start_time", ">=", pastThreeMonth).Documents(ctx)
	for {
		doc, err := iter.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return err
		}
		var video models.Video
		doc.DataTo(&video)
		for _, tag := range video.HashTags {
			emit(tag)
		}
	}
	return nil
}

func (f *getHashtagsFn) FinishBundle(ctx context.Context, emit func(string)) error {
	return f.client.Close()
}

type HashtagCount struct {
	Hashtag string
	Count   int64
	Vector  []float32
}

func mapFn(s string, emit func(x string, y int64)) {
	emit(s, 1)
}

func combineFn(a, b int64) int64 {
	return a + b
}

type mapHashTagCount struct {
	client *aiplatform.PredictionClient
	cfg    Config
}

func (f *mapHashTagCount) StartBundle(ctx context.Context, emit func(HashtagCount)) error {
	var err error
	f.cfg, err = Environ()
	if err != nil {
		return err
	}
	f.client, err = aiplatform.NewPredictionClient(ctx, option.WithEndpoint(f.cfg.AIEndpoint()))
	return err
}

func (f *mapHashTagCount) ProcessElement(ctx context.Context, s string, count int64, emit func(HashtagCount)) error {
	if count < tagCountThreshold {
		return nil
	}
	instances := make([]*structpb.Value, 1)
	instances[0] = structpb.NewStructValue(&structpb.Struct{
		Fields: map[string]*structpb.Value{
			"content":   structpb.NewStringValue(s),
			"task_type": structpb.NewStringValue("SEMANTIC_SIMILARITY"),
		},
	})
	params := structpb.NewStructValue(&structpb.Struct{
		Fields: map[string]*structpb.Value{
			"outputDimensionality": structpb.NewNumberValue(float64(dimensionality)),
		},
	})
	req := &aiplatformpb.PredictRequest{
		Endpoint:   f.cfg.EmbeddingModelEndpoint(),
		Instances:  instances,
		Parameters: params,
	}
	resp, err := f.client.Predict(ctx, req)
	if err != nil {
		return err
	}
	if len(resp.Predictions) <= 0 {
		return errors.New("no predictions")
	}
	embeddings := make([][]float32, len(resp.Predictions))
	for i, prediction := range resp.Predictions {
		values := prediction.GetStructValue().Fields["embeddings"].GetStructValue().Fields["values"].GetListValue().Values
		embeddings[i] = make([]float32, len(values))
		for j, value := range values {
			embeddings[i][j] = float32(value.GetNumberValue())
		}
	}
	emit(HashtagCount{
		Hashtag: s,
		Count:   count,
		Vector:  embeddings[0],
	})
	return nil
}

func (f *mapHashTagCount) FinishBundle(ctx context.Context, emit func(HashtagCount)) error {
	return f.client.Close()
}

type HashTagGroup struct {
	Centroid HashtagCount
	Hashtags []HashtagCount
}

func (g HashTagGroup) Merge(other HashTagGroup) HashTagGroup {
	if g.Centroid.Count > other.Centroid.Count {
		g.Hashtags = append(g.Hashtags, other.Hashtags...)
		return g
	}
	other.Hashtags = append(other.Hashtags, g.Hashtags...)
	return other
}

type HashTagGroupAccumulator struct {
	Groups []HashTagGroup
}

func (acc HashTagGroupAccumulator) findClosest(tag HashtagCount) (int, bool) {
	target := 0
	var maxDistance float32
	for i, group := range acc.Groups {
		if d := distance(group.Centroid.Vector, tag.Vector); d >= maxDistance {
			maxDistance = d
			target = i
		}
	}
	return target, maxDistance > distanceThreshold
}

type clusterFn struct{}

func (fn *clusterFn) CreateAccumulator() HashTagGroupAccumulator {
	return HashTagGroupAccumulator{}
}

func (fn *clusterFn) AddInput(acc HashTagGroupAccumulator, tag HashtagCount) HashTagGroupAccumulator {
	i, ok := acc.findClosest(tag)
	if ok {
		acc.Groups[i].Hashtags = append(acc.Groups[i].Hashtags, tag)
		if tag.Count > acc.Groups[i].Centroid.Count {
			acc.Groups[i].Centroid = tag
		}
		return acc
	}
	acc.Groups = append(acc.Groups, HashTagGroup{
		Centroid: tag,
		Hashtags: []HashtagCount{tag},
	})
	return acc
}

func (fn *clusterFn) MergeAccumulators(a, b HashTagGroupAccumulator) HashTagGroupAccumulator {
	var groups []HashTagGroup
	for _, group := range b.Groups {
		i, ok := a.findClosest(group.Centroid)
		if ok {
			a.Groups[i] = a.Groups[i].Merge(group)
			continue
		}
		groups = append(groups, group)
	}
	a.Groups = append(a.Groups, groups...)
	return a
}

func (fn *clusterFn) ExtractOutput(acc HashTagGroupAccumulator) []HashTagGroup {
	return acc.Groups
}

func (fn *clusterFn) Compact(acc HashTagGroupAccumulator) HashTagGroupAccumulator {
	return acc
}

func flattenGroupsFn(groups []HashTagGroup, emit func(HashTagGroup)) {
	for _, group := range groups {
		log.Println(group)
		emit(group)
	}
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

type summaryHashTagsFn struct {
	cfg    Config
	client *firestore.Client
}

func (fn *summaryHashTagsFn) StartBundle(ctx context.Context, emit func(HashTagGroup)) error {
	app, err := firebase.NewApp(ctx, nil)
	if err != nil {
		return err
	}
	fn.client, err = app.Firestore(ctx)
	if err != nil {
		return err
	}
	fn.cfg, err = Environ()
	if err != nil {
		return err
	}
	return nil
}

func (fn *summaryHashTagsFn) FinishBundle(ctx context.Context, emit func(HashTagGroup)) error {
	if err := fn.client.Close(); err != nil {
		return err
	}
	return nil
}

func (fn *summaryHashTagsFn) ProcessElement(ctx context.Context, group HashTagGroup, emit func(HashTagGroup)) error {
	slices.SortFunc(group.Hashtags, func(i, j HashtagCount) int {
		if i.Count > j.Count {
			return -1
		} else if i.Count < j.Count {
			return 1
		}
		return 0
	})
	var tags []string
	var documents int64
	for _, tag := range group.Hashtags[:minInt(30, len(group.Hashtags))] {
		tags = append(tags, tag.Hashtag)
		documents += tag.Count
	}
	if documents < documentThreshold {
		return nil
	}
	doc := make(map[string]interface{})
	doc["summarized"] = false
	doc["tags"] = tags
	doc["timestamp"] = firestore.ServerTimestamp
	_, _, err := fn.client.Collection("topics").Add(ctx, doc)
	if err != nil {
		return err
	}
	emit(group)
	return nil
}

func formatFn(group HashTagGroup) string {
	var tags []string
	for _, tag := range group.Hashtags {
		tags = append(tags, tag.Hashtag)
	}
	o, _ := json.Marshal(tags)
	return string(o)
}

func distance(a, b []float32) float32 {
	var sum float32
	for i := range a {
		sum += a[i] * b[i]
	}
	return sum
}

func runTeardownTask(ctx context.Context) error {
	cfg, err := Environ()
	if err != nil {
		return err
	}
	url := fmt.Sprintf("https://%s-%s.cloudfunctions.net/%s", cfg.Location, cfg.Project, teardownTaskName)
	client, err := idtoken.NewClient(ctx, url)
	if err != nil {
		return err
	}
	resp, err := client.Post(url, "application/json", nil)
	if err != nil {
		return err
	}
	if resp.StatusCode != 200 {
		return fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}
	return nil
}

type teardownFn struct{}

func (fn *teardownFn) ProcessElement(ctx context.Context, _ int, lines func(*string) bool) error {
	var line string
	for lines(&line) {
		log.Println(line)
	}
	return runTeardownTask(ctx)
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
	hashtag := beam.ParDo(s, &getHashtagsFn{}, impulse)
	counted := beam.ParDo(s, mapFn, hashtag)
	summed := beam.CombinePerKey(s, combineFn, counted)
	hashtagCount := beam.ParDo(s, &mapHashTagCount{}, summed)
	clusterred := beam.Combine(s, &clusterFn{}, hashtagCount)
	groups := beam.ParDo(s, flattenGroupsFn, clusterred)
	summarized := beam.ParDo(s, &summaryHashTagsFn{}, groups)
	formatted := beam.ParDo(s, formatFn, summarized)
	Teardown(s, formatted)

	ctx := context.Background()

	if err := beamx.Run(ctx, p); err != nil {
		log.Fatal(err)
	}
}
