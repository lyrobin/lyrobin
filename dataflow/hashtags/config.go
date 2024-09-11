package main

import (
	"fmt"

	"github.com/kelseyhightower/envconfig"
)

type Config struct {
	Location       string `envconfig:"LOCATION" default:"us-central1"`
	Project        string `envconfig:"GCLOUD_PROJECT" default:"taiwan-legislative-search"`
	EmbeddingModel string `envconfig:"EMBEDDING_MODEL" default:"text-multilingual-embedding-002"`
	GenAiModel     string `envconfig:"GEN_AI_MODEL" default:"gemini-1.5-flash-001"`
}

func Environ() (Config, error) {
	cfg := Config{}
	err := envconfig.Process("", &cfg)
	return cfg, err
}

func (c Config) AIEndpoint() string {
	return c.Location + "-aiplatform.googleapis.com:443"
}

func (c Config) EmbeddingModelEndpoint() string {
	return fmt.Sprintf("projects/%s/locations/%s/publishers/google/models/%s", c.Project, c.Location, c.EmbeddingModel)
}
