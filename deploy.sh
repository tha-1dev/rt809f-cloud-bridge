#!/bin/bash
# deploy.sh - RT809F Cloud Bridge Deployment

echo "🚀 RT809F Cloud Bridge Deployment Script"
echo "========================================"

# Configuration
PROJECT_ID="pmic-thai-dev"
REGION="asia-southeast1"
SERVICE_NAME="rt809f-bridge"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Google Cloud SDK not found. Please install:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Authenticate
echo "🔐 Authenticating with Google Cloud..."
gcloud auth login

# Set project
echo "📁 Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "⚙️ Enabling required APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com

# Build and deploy
echo "🏗️ Building and deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --max-instances 10 \
    --timeout 300 \
    --port 8080

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region $REGION \
    --format 'value(status.url)')

echo ""
echo "✅ Deployment Complete!"
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "📡 Endpoints:"
echo "   Web UI: $SERVICE_URL"
echo "   Health: $SERVICE_URL/health"
echo "   API: $SERVICE_URL/docs"
echo "   WebSocket: ${SERVICE_URL/https/ws}/ws/device/rt809f_001"
echo ""
echo "🔧 To update deployment, run: ./deploy.sh"