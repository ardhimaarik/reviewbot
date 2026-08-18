package webhook

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
)

type PREvent struct {
	Action string `json:"action"`
	Number int    `json:"number"`
	PullRequest struct {
		Title string `json:"title"`
		Head  struct {
			SHA  string `json:"sha"`
			Ref  string `json:"ref"`
		} `json:"head"`
	} `json:"pull_request"`
	Repository struct {
		FullName string `json:"full_name"`
		CloneURL string `json:"clone_url"`
	} `json:"repository"`
	Installation struct {
		ID int64 `json:"id"`
	} `json:"installation"`
}

type Handler struct {
	webhookSecret string
	reviewHandler func(event PREvent) error
}

func New(reviewHandler func(event PREvent) error) *Handler {
	return &Handler{
		webhookSecret: os.Getenv("GITHUB_WEBHOOK_SECRET"),
		reviewHandler: reviewHandler,
	}
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Read body
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "failed to read body", http.StatusBadRequest)
		return
	}

	// Verify signature
	if err := h.verifySignature(r.Header.Get("X-Hub-Signature-256"), body); err != nil {
		log.Printf("Webhook signature verification failed: %v", err)
		http.Error(w, "invalid signature", http.StatusUnauthorized)
		return
	}

	// Only handle pull_request events
	eventType := r.Header.Get("X-GitHub-Event")
	if eventType != "pull_request" {
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"message": "event %s ignored"}`, eventType)
		return
	}

	// Parse payload
	var event PREvent
	if err := json.Unmarshal(body, &event); err != nil {
		http.Error(w, "failed to parse payload", http.StatusBadRequest)
		return
	}

	// Only handle opened + synchronize actions
	if event.Action != "opened" && event.Action != "synchronize" {
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"message": "action %s ignored"}`, event.Action)
		return
	}

	log.Printf("PR event: action=%s repo=%s pr=%d", event.Action, event.Repository.FullName, event.Number)

	// Respond immediately — process async
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"message": "review queued"}`)

	// Process in background
	go func() {
		if err := h.reviewHandler(event); err != nil {
			log.Printf("Review failed for PR #%d: %v", event.Number, err)
		}
	}()
}

func (h *Handler) verifySignature(signature string, body []byte) error {
	if h.webhookSecret == "" {
		return fmt.Errorf("webhook secret not configured")
	}

	mac := hmac.New(sha256.New, []byte(h.webhookSecret))
	mac.Write(body)
	expected := "sha256=" + hex.EncodeToString(mac.Sum(nil))

	if !hmac.Equal([]byte(signature), []byte(expected)) {
		return fmt.Errorf("signature mismatch: got %s, want %s", signature, expected)
	}
	return nil
}

// ParseOwnerRepo splits "owner/repo" into owner, repo
func ParseOwnerRepo(fullName string) (string, string) {
	parts := strings.SplitN(fullName, "/", 2)
	if len(parts) != 2 {
		return "", ""
	}
	return parts[0], parts[1]
}
