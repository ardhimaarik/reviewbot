package review

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	githubclient "github.com/ardhimaarik/reviewbot/internal/github"
	"github.com/ardhimaarik/reviewbot/internal/storage"
	"github.com/ardhimaarik/reviewbot/internal/webhook"
)

type AIReviewRequest struct {
	Diff      string   `json:"diff"`
	FilePaths []string `json:"file_paths"`
	RepoPath  string   `json:"repo_path"`
	Model     string   `json:"model"`
}

type AIReviewResponse struct {
	Review struct {
		Summary string `json:"summary"`
		Issues  []struct {
			Severity   string  `json:"severity"`
			Category   string  `json:"category"`
			File       string  `json:"file"`
			Line       int     `json:"line"`
			Message    string  `json:"message"`
			Suggestion string  `json:"suggestion"`
			Confidence float64 `json:"confidence"`
		} `json:"issues"`
	} `json:"review"`
	LinterIssues []interface{} `json:"linter_issues"`
	LatencyMS    int           `json:"latency_ms"`
}

type Orchestrator struct {
	ghClient     *githubclient.Client
	db           *storage.DB
	aiServiceURL string
}

func New(ghClient *githubclient.Client, db *storage.DB) *Orchestrator {
	aiURL := os.Getenv("AI_SERVICE_URL")
	if aiURL == "" {
		aiURL = "http://localhost:8081"
	}
	return &Orchestrator{
		ghClient:     ghClient,
		db:           db,
		aiServiceURL: aiURL,
	}
}

func (o *Orchestrator) HandlePREvent(event webhook.PREvent) error {
	ctx := context.Background()
	owner, repo := webhook.ParseOwnerRepo(event.Repository.FullName)
	if owner == "" {
		return fmt.Errorf("invalid repo full name: %s", event.Repository.FullName)
	}

	log.Printf("Processing PR #%d in %s/%s", event.Number, owner, repo)

	// 1. Fetch diff from GitHub
	diff, filePaths, err := o.ghClient.GetPRDiff(ctx, owner, repo, event.Number)
	if err != nil {
		return fmt.Errorf("failed to get PR diff: %v", err)
	}

	if diff == "" {
		log.Printf("PR #%d has no diff, skipping", event.Number)
		return nil
	}

	log.Printf("Got diff: %d chars, %d files", len(diff), len(filePaths))

	// 2. Call AI service
	start := time.Now()
	aiResp, err := o.callAIService(diff, filePaths)
	if err != nil {
		return fmt.Errorf("AI service failed: %v", err)
	}
	latencyMS := int(time.Since(start).Milliseconds())

	log.Printf("AI review complete: %d issues, %dms", len(aiResp.Review.Issues), latencyMS)

	// 3. Format comment
	comment := formatComment(aiResp)

	// 4. Post to GitHub
	prURL := fmt.Sprintf("https://github.com/%s/%s/pull/%d", owner, repo, event.Number)
	if err := o.ghClient.PostReviewComment(ctx, owner, repo, event.Number, comment); err != nil {
		return fmt.Errorf("failed to post comment: %v", err)
	}

	log.Printf("Posted review comment to PR #%d", event.Number)

	// 5. Save to Postgres
	_, err = o.db.SaveReview(storage.Review{
		PRURL:         prURL,
		PRNumber:      event.Number,
		Repo:          event.Repository.FullName,
		Model:         "qwen3.5:9b",
		PromptVersion: "v1",
		RouteDecision: "simple",
		LatencyMS:     latencyMS,
		LinterIssues:  aiResp.LinterIssues,
		LLMOutput:     aiResp.Review,
		Posted:        true,
	})
	if err != nil {
		log.Printf("Failed to save review to DB: %v", err)
		// Don't return error — review was already posted
	}

	return nil
}

func (o *Orchestrator) callAIService(diff string, filePaths []string) (*AIReviewResponse, error) {
	reqBody := AIReviewRequest{
		Diff:      diff,
		FilePaths: filePaths,
		RepoPath:  ".",
		Model:     "qwen3.5:9b",
	}

	bodyBytes, _ := json.Marshal(reqBody)

	resp, err := http.Post(
		o.aiServiceURL+"/review",
		"application/json",
		bytes.NewReader(bodyBytes),
	)
	if err != nil {
		return nil, fmt.Errorf("HTTP call failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI service returned %d", resp.StatusCode)
	}

	var aiResp AIReviewResponse
	if err := json.NewDecoder(resp.Body).Decode(&aiResp); err != nil {
		return nil, fmt.Errorf("failed to decode AI response: %v", err)
	}

	return &aiResp, nil
}

func formatComment(resp *AIReviewResponse) string {
	var sb strings.Builder

	sb.WriteString("## 🤖 Reviewbot AI Review\n\n")
	sb.WriteString(fmt.Sprintf("**Summary:** %s\n\n", resp.Review.Summary))

	if len(resp.Review.Issues) == 0 {
		sb.WriteString("✅ No significant issues found.\n")
		return sb.String()
	}

	sb.WriteString(fmt.Sprintf("Found **%d issue(s)**:\n\n", len(resp.Review.Issues)))

	for i, issue := range resp.Review.Issues {
		emoji := severityEmoji(issue.Severity)
		sb.WriteString(fmt.Sprintf("### %s Issue %d: %s (%s)\n", emoji, i+1, issue.Category, issue.Severity))
		sb.WriteString(fmt.Sprintf("**File:** `%s` line %d\n\n", issue.File, issue.Line))
		sb.WriteString(fmt.Sprintf("**Problem:** %s\n\n", issue.Message))
		sb.WriteString(fmt.Sprintf("**Suggestion:** %s\n\n", issue.Suggestion))
		sb.WriteString(fmt.Sprintf("*Confidence: %.0f%%*\n\n", issue.Confidence*100))
		sb.WriteString("---\n\n")
	}

	sb.WriteString("*Reviewed by [Reviewbot](https://github.com/ardhimaarik/reviewbot) — AI-powered PR reviewer*")
	return sb.String()
}

func severityEmoji(severity string) string {
	switch severity {
	case "blocker":
		return "🔴"
	case "major":
		return "🟠"
	case "minor":
		return "🟡"
	case "nit":
		return "🔵"
	default:
		return "⚪"
	}
}
