package config

import "github.com/kelseyhightower/envconfig"

type Config struct {
	Server      Server
	TypeSense   TypeSense
	Legislative Legislative
}

type Server struct {
	Port string `envconfig:"PORT" default:"8080"`
}

type TypeSense struct {
	Host     string `envconfig:"TYPESENSE_HOST" default:"localhost"`
	Port     string `envconfig:"TYPESENSE_PORT" default:"8108"`
	Protocol string `envconfig:"TYPESENSE_PROTOCOL" default:"http"`
	Key      string `envconfig:"TYPESENSE_API_KEY" default:"xyz"`
}

type Legislative struct {
	Domain string `envconfig:"LEGISLATIVE_DOMAIN" default:"https://ppg.ly.gov.tw"`
}

func Environ() (Config, error) {
	cfg := Config{}
	err := envconfig.Process("", &cfg)
	return cfg, err
}
