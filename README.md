# TikTok Workout Parser - AI Powered

API that takes a TikTok URL and returns structured workout JSON in ~3 minutes using Google Gen AI.

## 🚀 Live API

**Production Endpoint:** https://tiktok-workout-parser-341666880405.us-central1.run.app

### Quick Test
```bash
# Health check
curl -X GET "https://tiktok-workout-parser-341666880405.us-central1.run.app/health"

# Process a video
curl -X POST "https://tiktok-workout-parser-341666880405.us-central1.run.app/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'
```

## 🏗️ Architecture

- **Backend**: FastAPI + Python 3.11
- **AI Model**: Google Gen AI (Gemini 2.0 Flash)
- **Deployment**: Google Cloud Run (Serverless)
- **Video Processing**: ffmpeg for audio removal
- **Video Scraping**: ScrapeCreators API

## 📋 How It Works

1. **Download TikTok Video** using ScrapeCreators API (no watermark)
2. **Extract Transcript** directly from video info response
3. **Remove Audio** from video using ffmpeg for faster processing
4. **Analyze Video + Transcript** with Google Gen AI (Gemini 2.0 Flash)
5. **Return Structured JSON** with workout details

## 🛠️ Local Development Setup

### 1. Prerequisites
- Python 3.11+
- Google Cloud CLI
- Docker (for deployment)
- ScrapeCreators API key

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file:
```env
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT_ID=sets-ai

# ScrapeCreators API Key (for TikTok video scraping)
SCRAPECREATORS_API_KEY=TqHKAnqkrYcEQDRFDf2mjyPawR43

# Optional: Set to 'production' for production environment
ENVIRONMENT=development
```

### 4. Google Cloud Setup

#### 4.1 Authentication
```bash
# Install Google Cloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Authenticate with your Google account
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project sets-ai
```

#### 4.2 Enable Required APIs
```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable storage.googleapis.com
```

### 5. Run Locally
```bash
python main.py
```

The API will be available at `http://localhost:8080`

## 🚀 Deployment to Google Cloud Run

### Option 1: Automated Deployment (Recommended)
```bash
# Deploy (project ID is already configured in deploy.sh)
./deploy.sh
```

### Option 2: Manual Deployment
```bash
# 1. Build and push Docker image
docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/sets-ai/tiktok-workout-parser/tiktok-workout-parser:latest \
  . --push

# 2. Deploy to Cloud Run
gcloud run deploy tiktok-workout-parser \
  --image us-central1-docker.pkg.dev/sets-ai/tiktok-workout-parser/tiktok-workout-parser:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --max-instances 10 \
  --set-env-vars GOOGLE_CLOUD_PROJECT_ID=sets-ai,SCRAPECREATORS_API_KEY=your_scrapecreators_api_key_here
```

### Option 3: Cloud Build (CI/CD)
```bash
# Deploy using Cloud Build
gcloud builds submit --config cloudbuild.yaml .
```

## 📚 API Reference

### Endpoints

#### `GET /health`
Health check endpoint.
```bash
curl -X GET "https://tiktok-workout-parser-341666880405.us-central1.run.app/health"
```
**Response:**
```json
{"status": "healthy"}
```

#### `POST /process`
Process a TikTok video and extract workout information.

**Request:**
```bash
curl -X POST "https://tiktok-workout-parser-341666880405.us-central1.run.app/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/1234567890"}'
```

**Response:**
```json
{
  "title": "Full Body HIIT Workout",
  "description": "Intense 15-minute full body workout",
  "workout_type": "hiit",
  "duration_minutes": 15,
  "difficulty_level": 8,
  "exercises": [
    {
      "name": "Burpees",
      "muscle_groups": ["full_body"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 15,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": 30
        }
      ],
      "instructions": "Start standing, drop to plank, do push-up, jump back up"
    }
  ],
  "tags": ["hiit", "cardio", "fullbody", "workout"],
  "creator": "@fitnessuser"
}
```

#### `GET /test-api`
Test the ScrapeCreators API connection.
```bash
curl -X GET "https://tiktok-workout-parser-341666880405.us-central1.run.app/test-api"
```

### Error Responses

| Status Code | Description |
|-------------|-------------|
| 400 | Invalid TikTok URL |
| 404 | TikTok video not found |
| 422 | Could not extract workout information |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

## 🔧 Development & Editing

### Project Structure
```
sets-ai-backend/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── cloudbuild.yaml        # Cloud Build configuration
├── deploy.sh              # Deployment script
├── src/
│   ├── services/
│   │   ├── genai_service.py    # Google Gen AI integration
│   │   └── tiktok_scraper.py   # TikTok video scraping
│   └── worker/
│       └── video_processor.py  # Video processing (ffmpeg)
└── README.md
```

### Making Changes

#### 1. Code Changes
- Edit files in `src/` directory
- Test locally with `python main.py`
- Update requirements.txt if adding new dependencies

#### 2. Environment Variables
- Update `.env` file for local development
- For production, update Cloud Run environment variables:
```bash
gcloud run services update tiktok-workout-parser \
  --region us-central1 \
  --set-env-vars NEW_VAR=value
```

#### 3. Docker Changes
- Modify `Dockerfile` for system dependencies
- Rebuild and redeploy:
```bash
docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/sets-ai/tiktok-workout-parser/tiktok-workout-parser:latest \
  . --push
```

#### 4. Redeploy
```bash
# Quick redeploy
./deploy.sh

# Or manual redeploy
gcloud run deploy tiktok-workout-parser \
  --image us-central1-docker.pkg.dev/sets-ai/tiktok-workout-parser/tiktok-workout-parser:latest \
  --region us-central1
```

### Testing

#### Local Testing
```bash
# Start the server
python main.py

# Test health endpoint
curl -X GET "http://localhost:8080/health"

# Test video processing
curl -X POST "http://localhost:8080/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/1234567890"}'
```

#### Production Testing
```bash
# Test the live API
curl -X GET "https://tiktok-workout-parser-341666880405.us-central1.run.app/health"

# Test video processing
curl -X POST "https://tiktok-workout-parser-341666880405.us-central1.run.app/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/1234567890"}'
```

## 💰 Cost Information

### Google Cloud Run Pricing
- **Free Tier**: 2 million requests/month
- **After Free Tier**: ~$0.40 per million requests
- **Compute**: ~$0.00002400 per 100ms of CPU time
- **Memory**: ~$0.00000250 per GB-second

### Estimated Monthly Costs
- **Low usage** (< 1000 requests): $0-5/month
- **Medium usage** (10,000 requests): $5-20/month
- **High usage** (100,000 requests): $20-100/month

## 🔒 Security

- ✅ **HTTPS**: Automatic SSL certificates
- ✅ **Environment Variables**: Secure API key storage
- ✅ **IAM Permissions**: Proper Google Cloud permissions
- ✅ **No Data Storage**: No persistent data storage
- ✅ **Rate Limiting**: Built-in retry logic with exponential backoff

## 🐛 Troubleshooting

### Common Issues

#### 1. Permission Denied (403)
```bash
# Grant Vertex AI permissions
gcloud projects add-iam-policy-binding sets-ai \
  --member="serviceAccount:341666880405-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

#### 2. Container Failed to Start
- Check environment variables are set
- Verify API keys are correct
- Check Cloud Run logs:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=tiktok-workout-parser" --limit=20
```

#### 3. Rate Limit Exceeded (429)
- The API includes automatic retry logic
- Wait a few minutes and try again
- Consider upgrading Google Cloud quotas

### Viewing Logs
```bash
# Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=tiktok-workout-parser" --limit=50

# Real-time logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=tiktok-workout-parser"
```

## 📈 Performance

- **Average Response Time**: 2-3 minutes
- **Video Processing**: ~30 seconds
- **AI Analysis**: ~1-2 minutes
- **Memory Usage**: 2GB allocated
- **CPU**: 2 cores allocated
- **Timeout**: 15 minutes maximum

1. Downloads TikTok video using ScrapCreators API (no watermark)
2. Extracts transcript directly from video info response (single API call)
3. Removes audio from video using ffmpeg
4. Analyzes silent video + transcript with Gemini 2.5 Flash
5. Returns structured workout JSON
