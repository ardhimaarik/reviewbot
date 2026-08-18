// service/cmd/reviewbot/main.go
package main

import (
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
)

func main() {
	// Server config
	port := os.Getenv("PORT")
	if port == "" {
		port = "8090"
	}

	aiService := os.Getenv("AI_SERVICE_URL")
	if aiService == "" {
		aiService = "http://localhost:8081"
	}

	// Gin setup
	if os.Getenv("ENVIRONMENT") == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	r := gin.Default()

	// Health check
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	// Webhook endpoint (stub for Week 1)
	r.POST("/webhook", func(c *gin.Context) {
		// Week 1: just accept and log
		// Week 2: actually process webhook
		c.JSON(http.StatusOK, gin.H{"message": "webhook received"})
		log.Printf("Webhook received from %s", c.RemoteIP())
	})

	// Metrics endpoint (stub for Week 3)
	r.GET("/metrics", func(c *gin.Context) {
		c.String(http.StatusOK, "# HELP reviewbot_reviews_total Total reviews processed\n")
	})

	// Start server
	addr := fmt.Sprintf(":%s", port)
	log.Printf("Starting Reviewbot API on %s (AI service: %s)", addr, aiService)
	if err := r.Run(addr); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
