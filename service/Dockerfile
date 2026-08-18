FROM golang:1.25-alpine

WORKDIR /app

RUN apk add --no-cache ca-certificates

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 go build -o reviewbot ./cmd/reviewbot

EXPOSE 8090

CMD ["./reviewbot"]
