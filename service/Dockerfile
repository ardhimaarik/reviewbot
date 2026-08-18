# service/Dockerfile
FROM golang:1.22-alpine as build

WORKDIR /build

# Install build deps
RUN apk add --no-cache git ca-certificates

# Copy go files
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# Build binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o reviewbot ./cmd/reviewbot

# Production image
FROM alpine:3.18 as production

RUN apk add --no-cache ca-certificates curl

WORKDIR /app

COPY --from=build /build/reviewbot .

EXPOSE 8090

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
	CMD curl -f http://localhost:8090/health || exit 1

CMD ["./reviewbot"]

# Dev image (with hot reload via air)
FROM golang:1.22-alpine as dev

WORKDIR /app

RUN apk add --no-cache curl ca-certificates

# Install air for hot reload
RUN go install github.com/cosmtrek/air@latest

EXPOSE 8090

CMD ["air", "-c", ".air.toml"]
