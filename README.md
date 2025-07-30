# TikTok Workout Parser

API that takes a TikTok URL and returns structured workout JSON in ~3 seconds.

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Google Cloud Setup

#### 2.1 Create Google Cloud Project
```bash
# Install Google Cloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Create a new project (replace YOUR_PROJECT_ID with your desired project ID)
gcloud projects create YOUR_PROJECT_ID

# Set as default project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable aiplatform.googleapis.com
```

#### 2.2 Authentication Setup

**Option A: Application Default Credentials (Recommended for development)**
```bash
# Authenticate with your Google account
gcloud auth application-default login
```

**Option B: Service Account (Recommended for production)**
```bash
# Create service account
gcloud iam service-accounts create tiktok-parser --display-name="TikTok Parser Service"

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:tiktok-parser@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Create and download key file
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account=tiktok-parser@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Environment Variables
Copy `env.example` to `.env` and fill in your values:

```bash
cp env.example .env
```

Edit `.env`:
```env
# ScrapeCreators API Configuration
SCRAPECREATORS_API_KEY=your_scrapecreators_api_key_here

# Google Cloud Configuration (REQUIRED)
GOOGLE_CLOUD_PROJECT_ID=your-google-cloud-project-id

# Optional: Service Account Key (if not using Application Default Credentials)
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### 4. Run the Application

**Quick Start (if you already have gcloud configured):**
```bash
./run.sh
```

**Manual Start:**
```bash
export GOOGLE_CLOUD_PROJECT_ID=sets-ai
python main.py
```

The API will be available at `http://localhost:8080`

### Quick Setup for Existing Google Cloud Users

If you already have Google Cloud CLI installed and authenticated:

1. **Check your setup:**
   ```bash
   gcloud config get-value project  # Should show your project ID
   gcloud auth application-default login  # If not already authenticated
   ```

2. **Install and run:**
   ```bash
   pip install -r requirements.txt
   cp env.example .env  # Add your SCRAPECREATORS_API_KEY
   ./run.sh
   ```

## Usage

```bash
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'
```

Returns workout JSON:
```json
{
  "title": "Full Body HIIT Workout",
  "workout_type": "hiit",
  "duration_minutes": 10,
  "difficulty_level": 7,
  "exercises": [
    {
      "name": "Burpees",
      "muscle_groups": ["full_body"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 15,
          "rest_seconds": 30
        }
      ]
    }
  ],
  "tags": ["hiit", "cardio", "fullbody"],
  "creator": "@fitnessuser"
}
```

## How it works

1. Downloads TikTok video using ScrapCreators API (no watermark)
2. Extracts transcript directly from video info response (single API call)
3. Removes audio from video using ffmpeg
4. Analyzes silent video + transcript with Gemini 2.5 Flash
5. Returns structured workout JSON

That's it. Fast.

## Features

- ✅ **Gemini 2.5 Flash**: Latest AI model with enhanced reasoning capabilities
- ✅ **Optimized API Calls**: Single request for video + transcript data
- ✅ **No Watermarks**: Clean video downloads via ScrapCreators
- ✅ **Silent Processing**: Audio removed for faster analysis
- ✅ **Structured Output**: Consistent JSON workout format
- ✅ **Error Handling**: Robust error handling and logging