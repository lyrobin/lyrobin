FROM golang:1.22-alpine as go-build

RUN mkdir -p /usr/src/app

COPY ./cloudrun/api-server /usr/src/app/cloudrun/api-server

COPY ./dataflow /usr/src/app/dataflow

COPY go.work go.work.sum /usr/src/app/

WORKDIR /usr/src/app/dataflow

RUN go mod download && go mod verify

RUN go build -v -o dataflow ./hashtags

FROM gcr.io/dataflow-templates-base/go-template-launcher-base

ARG WORKDIR=/dataflow/template
ARG PROJECT_ID=taiwan-legislative-search
ARG LOCATION=asia-east1
RUN mkdir -p ${WORKDIR}

COPY --from=go-build /usr/src/app/dataflow/dataflow ${WORKDIR}/dataflow

ENV FLEX_TEMPLATE_GO_BINARY="${WORKDIR}/dataflow"
ENV FIREBASE_CONFIG="{\"projectId\":\"${PROJECT_ID}\",\"storageBucket\":\"${PROJECT_ID}.appspot.com\",\"locationId\":\"${LOCATION}\"}"
ENV GCLOUD_PROJECT="${PROJECT_ID}"

ENTRYPOINT ["/opt/google/dataflow/go_template_launcher"]
