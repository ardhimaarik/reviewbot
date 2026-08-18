package storage

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"time"

	_ "github.com/lib/pq"
)

type DB struct {
	db *sql.DB
}

type Review struct {
	PRURL         string
	PRNumber      int
	Repo          string
	Model         string
	PromptVersion string
	RouteDecision string
	LatencyMS     int
	LinterIssues  interface{}
	LLMOutput     interface{}
	Posted        bool
	Hallucinations int
}

func New() (*DB, error) {
	dsn := os.Getenv("POSTGRES_DSN")
	if dsn == "" {
		return nil, fmt.Errorf("POSTGRES_DSN not set")
	}

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to open DB: %v", err)
	}

	// Test connection with retry
	for i := 0; i < 5; i++ {
		if err := db.Ping(); err == nil {
			break
		}
		time.Sleep(2 * time.Second)
	}

	return &DB{db: db}, nil
}

func (d *DB) SaveReview(r Review) (int64, error) {
	linterJSON, _ := json.Marshal(r.LinterIssues)
	llmJSON, _ := json.Marshal(r.LLMOutput)

	var id int64
	err := d.db.QueryRow(`
		INSERT INTO reviews 
			(pr_url, pr_number, repo, model, prompt_version, route_decision,
			 latency_ms, linter_issues, llm_output, posted, hallucinations)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
		RETURNING id`,
		r.PRURL, r.PRNumber, r.Repo, r.Model, r.PromptVersion,
		r.RouteDecision, r.LatencyMS, linterJSON, llmJSON, r.Posted, r.Hallucinations,
	).Scan(&id)
	return id, err
}
