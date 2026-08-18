package main

import (
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
	githubclient "github.com/ardhimaarik/reviewbot/internal/github"
	"github.com/ardhimaarik/reviewbot/internal/review"
	"github.com/ardhimaarik/reviewbot/internal/storage"
	"github.com/ardhimaarik/reviewbot/internal/webhook"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8090"
	}

	if os.Getenv("ENVIRONMENT") == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	// Init dependencies
	db, err := storage.New()
	if err != nil {
		log.Fatalf("Failed to connect to DB: %v", err)
	}
	log.Println("✅ Postgres connected")

	ghClient, err := githubclient.New()
	if err != nil {
		log.Fatalf("Failed to init GitHub client: %v", err)
	}
	log.Println("✅ GitHub App client initialized")

	orchestrator := review.New(ghClient, db)
	webhookHandler := webhook.New(orchestrator.HandlePREvent)

	// Gin router
	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	r.POST("/webhook", func(c *gin.Context) {
		webhookHandler.ServeHTTP(c.Writer, c.Request)
	})

	r.GET("/metrics", func(c *gin.Context) {
		c.String(http.StatusOK, "# metrics placeholder\n")
	})

	addr := fmt.Sprintf(":%s", port)
	log.Printf("🚀 Reviewbot API starting on %s", addr)
	if err := r.Run(addr); err != nil {
		log.Fatalf("Failed to start: %v", err)
	}
}
