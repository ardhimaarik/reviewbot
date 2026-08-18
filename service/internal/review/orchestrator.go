package review

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
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

type AIIssue struct {
	Severity   string  `json:"severity"`
	Category   string  `json:"category"`
	File       string  `json:"file"`
	Line       int     `json:"line"`
	Message    string  `json:"message"`
	Suggestion string  `json:"suggestion"`
	Confidence float64 `json:"confidence"`
}

type AIReviewResponse struct {
	Review struct {
		Summary string    `json:"summary"`
		Issues  []AIIssue `json:"issues"`
	} `json:"review"`
	LinterIssues []interface{} `json:"linter_issues"`
	LatencyMS    int           `json:"latency_ms"`
}

type Orchestrator struct {
	ghClient            *githubclient.Client
	db                  *storage.DB
	aiServiceURL        string
	confidenceThreshold float64
}

func New(ghClient *githubclient.Client, db *storage.DB) *Orchestrator {
	threshold := 0.7
	if t := os.Getenv("CONFIDENCE_THRESHOLD"); t != "" {
		if parsed, err := strconv.ParseFloat(t, 64); err == nil {
			threshold = parsed
		}
	}
	aiURL := os.Getenv("AI_SERVICE_URL")
	if aiURL == "" {
		aiURL = "http://localhost:8081"
	}
	return &Orchestrator{
		ghClient:            ghClient,
		db:                  db,
		aiServiceURL:        aiURL,
		confidenceThreshold: threshold,
	}
}

func (o *Orchestrator) HandlePREvent(event webhook.PREvent) error {
	ctx := context.Background()
	owner, repo := webhook.ParseOwnerRepo(event.Repository.FullName)
	if owner == "" {
		return fmt.Errorf("invalid repo: %s", event.Repository.FullName)
	}

	log.Printf("Processing PR #%d in %s/%s", event.Number, owner, repo)

	diff, filePaths, err := o.ghClient.GetPRDiff(ctx, owner, repo, event.Number)
	if err != nil {
		return fmt.Errorf("get diff: %v", err)
	}
	if diff == "" {
		log.Printf("PR #%d has no diff, skipping", event.Number)
		return nil
	}

	start := time.Now()
	aiResp, err := o.callAIService(diff, filePaths)
	if err != nil {
		return fmt.Errorf("AI service: %v", err)
	}
	latencyMS := int(time.Since(start).Milliseconds())

	allIssues := aiResp.Review.Issues
	log.Printf("AI found %d total issues in %dms", len(allIssues), latencyMS)

	// Confidence gating
	filtered := []AIIssue{}
	dropped := 0
	for _, iss := range allIssues {
		if iss.Confidence >= o.confidenceThreshold {
			filtered = append(filtered, iss)
		} else {
			dropped++
		}
	}
	log.Printf("Confidence gate (%.1f): kept %d, dropped %d issues",
		o.confidenceThreshold, len(filtered), dropped)

	// Hallucination check
	diffFiles := extractDiffFiles(diff)
	hallucinations := 0
	clean := []AIIssue{}
	for _, iss := range filtered {
		if len(diffFiles) > 0 && iss.File != "" {
			if _, ok := diffFiles[iss.File]; !ok {
				log.Printf("Hallucination: %s not in diff", iss.File)
				hallucinations++
				continue
			}
		}
		clean = append(clean, iss)
	}

	if hallucinations > 0 {
		log.Printf("Dropped %d hallucinated issues", hallucinations)
	}

	prURL := fmt.Sprintf("https://github.com/%s/%s/pull/%d", owner, repo, event.Number)
	comment := formatComment(aiResp.Review.Summary, clean, dropped)

	if err := o.ghClient.PostReviewComment(ctx, owner, repo, event.Number, comment); err != nil {
		return fmt.Errorf("post comment: %v", err)
	}
	log.Printf("Posted review to PR #%d (%d issues after filtering)", event.Number, len(clean))

	aiResp.Review.Issues = clean
	_, err = o.db.SaveReview(storage.Review{
		PRURL:          prURL,
		PRNumber:       event.Number,
		Repo:           event.Repository.FullName,
		Model:          "qwen3.5:9b",
		PromptVersion:  "v1",
		RouteDecision:  "simple",
		LatencyMS:      latencyMS,
		LinterIssues:   aiResp.LinterIssues,
		LLMOutput:      aiResp.Review,
		Posted:         true,
		Hallucinations: hallucinations,
	})
	if err != nil {
		log.Printf("DB save failed: %v", err)
	}

	return nil
}

func (o *Orchestrator) callAIService(diff string, filePaths []string) (*AIReviewResponse, error) {
	reqBody := AIReviewRequest{
		Diff: diff, FilePaths: filePaths, RepoPath: ".", Model: "qwen3.5:9b",
	}
	bodyBytes, _ := json.Marshal(reqBody)
	resp, err := http.Post(o.aiServiceURL+"/review", "application/json", bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI service %d", resp.StatusCode)
	}
	var aiResp AIReviewResponse
	if err := json.NewDecoder(resp.Body).Decode(&aiResp); err != nil {
		return nil, err
	}
	return &aiResp, nil
}

func extractDiffFiles(diff string) map[string]bool {
	files := map[string]bool{}
	for _, line := range strings.Split(diff, "\n") {
		if strings.HasPrefix(line, "+++ b/") {
			files[line[6:]] = true
		}
	}
	return files
}

func formatComment(summary string, issues []AIIssue, dropped int) string {
	var sb strings.Builder
	sb.WriteString("## 🤖 Reviewbot AI Review\n\n")
	sb.WriteString(fmt.Sprintf("**Summary:** %s\n\n", summary))
	if dropped > 0 {
		sb.WriteString(fmt.Sprintf("*%d low-confidence issue(s) filtered out.*\n\n", dropped))
	}
	if len(issues) == 0 {
		sb.WriteString("✅ No significant issues found.\n")
	} else {
		sb.WriteString(fmt.Sprintf("Found **%d issue(s)**:\n\n", len(issues)))
		for i, iss := range issues {
			emoji := severityEmoji(iss.Severity)
			sb.WriteString(fmt.Sprintf("### %s Issue %d: %s (%s)\n", emoji, i+1, iss.Category, iss.Severity))
			sb.WriteString(fmt.Sprintf("**File:** `%s` line %d\n\n", iss.File, iss.Line))
			sb.WriteString(fmt.Sprintf("**Problem:** %s\n\n", iss.Message))
			sb.WriteString(fmt.Sprintf("**Suggestion:** %s\n\n", iss.Suggestion))
			sb.WriteString(fmt.Sprintf("*Confidence: %.0f%%*\n\n", iss.Confidence*100))
			sb.WriteString("---\n\n")
		}
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
