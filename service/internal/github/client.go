package github

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/golang-jwt/jwt/v5"
	gh "github.com/google/go-github/v65/github"
)

type Client struct {
	appID          int64
	privateKeyPath string
	installationID int64
}

func New() (*Client, error) {
	appIDStr := os.Getenv("GITHUB_APP_ID")
	appID, err := strconv.ParseInt(appIDStr, 10, 64)
	if err != nil {
		return nil, fmt.Errorf("invalid GITHUB_APP_ID: %v", err)
	}

	installIDStr := os.Getenv("GITHUB_APP_INSTALLATION_ID")
	installID, err := strconv.ParseInt(installIDStr, 10, 64)
	if err != nil {
		return nil, fmt.Errorf("invalid GITHUB_APP_INSTALLATION_ID: %v", err)
	}

	return &Client{
		appID:          appID,
		privateKeyPath: os.Getenv("GITHUB_APP_PRIVATE_KEY_PATH"),
		installationID: installID,
	}, nil
}

// getInstallationToken generates a short-lived installation token
func (c *Client) getInstallationToken(ctx context.Context) (string, error) {
	// Read private key
	keyData, err := os.ReadFile(c.privateKeyPath)
	if err != nil {
		return "", fmt.Errorf("failed to read private key: %v", err)
	}

	// Parse private key
	privateKey, err := jwt.ParseRSAPrivateKeyFromPEM(keyData)
	if err != nil {
		return "", fmt.Errorf("failed to parse private key: %v", err)
	}

	// Generate JWT
	now := time.Now()
	claims := jwt.MapClaims{
		"iat": now.Unix(),
		"exp": now.Add(10 * time.Minute).Unix(),
		"iss": strconv.FormatInt(c.appID, 10),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	jwtToken, err := token.SignedString(privateKey)
	if err != nil {
		return "", fmt.Errorf("failed to sign JWT: %v", err)
	}

	// Exchange JWT for installation token
	jwtClient := gh.NewClient(&http.Client{
		Transport: &jwtTransport{token: jwtToken},
	})

	installToken, _, err := jwtClient.Apps.CreateInstallationToken(
		ctx,
		c.installationID,
		nil,
	)
	if err != nil {
		return "", fmt.Errorf("failed to create installation token: %v", err)
	}

	return installToken.GetToken(), nil
}

func (c *Client) ghClient(ctx context.Context) (*gh.Client, error) {
	token, err := c.getInstallationToken(ctx)
	if err != nil {
		return nil, err
	}
	return gh.NewClient(&http.Client{
		Transport: &tokenTransport{token: token},
	}), nil
}

// GetPRDiff fetches the diff for a pull request
func (c *Client) GetPRDiff(ctx context.Context, owner, repo string, prNumber int) (string, []string, error) {
	client, err := c.ghClient(ctx)
	if err != nil {
		return "", nil, err
	}

	// Get changed files
	files, _, err := client.PullRequests.ListFiles(ctx, owner, repo, prNumber, nil)
	if err != nil {
		return "", nil, fmt.Errorf("failed to list PR files: %v", err)
	}

	var diff string
	var filePaths []string
	for _, f := range files {
		filePaths = append(filePaths, f.GetFilename())
		if f.GetPatch() != "" {
			diff += fmt.Sprintf("diff --git a/%s b/%s\n%s\n", f.GetFilename(), f.GetFilename(), f.GetPatch())
		}
	}

	return diff, filePaths, nil
}

// PostReviewComment posts a review comment to a PR
func (c *Client) PostReviewComment(ctx context.Context, owner, repo string, prNumber int, body string) error {
	client, err := c.ghClient(ctx)
	if err != nil {
		return err
	}

	review := &gh.PullRequestReviewRequest{
		Body:  gh.String(body),
		Event: gh.String("COMMENT"),
	}

	_, _, err = client.PullRequests.CreateReview(ctx, owner, repo, prNumber, review)
	return err
}

// JWT transport helpers
type jwtTransport struct{ token string }

func (t *jwtTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	req.Header.Set("Authorization", "Bearer "+t.token)
	req.Header.Set("Accept", "application/vnd.github+json")
	return http.DefaultTransport.RoundTrip(req)
}

type tokenTransport struct{ token string }

func (t *tokenTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	req.Header.Set("Authorization", "token "+t.token)
	req.Header.Set("Accept", "application/vnd.github+json")
	return http.DefaultTransport.RoundTrip(req)
}
