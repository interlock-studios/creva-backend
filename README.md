# TikTok Workout Parser - AI Powered

**Turn any TikTok workout video into structured workout data in 3 minutes!**

This API takes a TikTok URL and automatically extracts:
- Exercise names and sets/reps
- Workout type and difficulty
- Equipment needed
- Duration and muscle groups
- Step-by-step instructions

## 🚀 Live Demo

**Try it now:** https://tiktok-workout-parser-341666880405.us-central1.run.app

**Quick test:**
```bash
curl -X POST "https://tiktok-workout-parser-341666880405.us-central1.run.app/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'
```

### What You Get Back

```json
{
  "title": "Updated Ab Routine",
  "description": "Bodyweight ab workout routine.",
  "workout_type": "bodyweight",
  "duration_minutes": 15,
  "difficulty_level": 7,
  "exercises": [
    {
      "name": "Deadbugs",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 20,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": "Keep your back flat and focus on breathing."
    },
    {
      "name": "Deadbugs (both legs)",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 20,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": "Keep your back flat and focus on breathing."
    },
    {
      "name": "Toe Touches",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 20,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": "Slow and controlled, should be engaging upper abs."
    },
    {
      "name": "Alternating Leg Lifts",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 20,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": null
    },
    {
      "name": "Leg Lifts",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 20,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": "Slow and back flat."
    },
    {
      "name": "Flutter Kicks",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 20,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": "Should be low to the ground."
    },
    {
      "name": "Slow Low Leg Raises",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 20,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": "Breathing and engaging lower abs."
    },
    {
      "name": "Slow Full Big Leg Circles",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 12,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": "No rest between legs."
    },
    {
      "name": "Forearm Plank",
      "muscle_groups": ["core", "full_body"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": null,
          "weight_lbs": null,
          "duration_seconds": 60,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": null
    },
    {
      "name": "Side Plank",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": null,
          "weight_lbs": null,
          "duration_seconds": 60,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": null
    },
    {
      "name": "Side Plank Pulses",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 30,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": null
    },
    {
      "name": "Plank Leg Raises",
      "muscle_groups": ["core", "glutes"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 30,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": null
    },
    {
      "name": "Plank Twists",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 30,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": null
    },
    {
      "name": "Plank Knee Taps",
      "muscle_groups": ["core"],
      "equipment": "bodyweight",
      "sets": [
        {
          "reps": 30,
          "weight_lbs": null,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": null
        }
      ],
      "instructions": null
    }
  ],
  "tags": [
    "abroutine",
    "abworkout",
    "sixpack",
    "workoutroutine",
    "gymgirl",
    "Fitness",
    "gym",
    "calisthenics",
    "pilates",
    "coreworkout"
  ],
  "creator": "haileyfernandes"
}
```

## 🛠️ How It Works

1. **You send a TikTok URL** → We download the video (no watermark!)
2. **We extract the transcript** → Get all the spoken instructions
3. **We remove the audio** → Makes AI analysis faster
4. **AI analyzes everything** → Google's Gemini AI understands the workout
5. **You get structured data** → Clean JSON with all the workout details

## 🏗️ Tech Stack

- **Backend**: FastAPI + Python 3.11
- **AI**: Google Gen AI (Gemini 2.0 Flash)
- **Hosting**: Google Cloud Run (serverless)
- **Video Processing**: ffmpeg
- **Video Scraping**: ScrapeCreators API



## 🚀 Quick Start (5 minutes)

### What You Need
- **Python 3.11** (download from python.org)
- **Google Cloud account** (free tier works)
- **ScrapeCreators API key** (get from scrapecreators.com)

### Step 1: Get Your API Key
1. Go to [scrapecreators.com](https://scrapecreators.com)
2. Sign up for a free account
3. Copy your API key

### Step 2: Clone & Setup
```bash
# Download this project
git clone <repository-url>
cd sets-ai-backend

# Run the setup (this does everything for you!)
make setup
```

### Step 3: Add Your API Key
```bash
# Edit the .env file with your API key
nano .env
# or use any text editor you like
```

Change this line:
```env
SCRAPECREATORS_API_KEY=your_actual_api_key_here
```

### Step 4: Run It!
```bash
# Start the app
make dev

# Your API is now running at http://localhost:8080
```

### Test Your Setup

Open a new terminal and try this:

```bash
# Test the health endpoint
curl http://localhost:8080/health

# Test with a real TikTok video
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'
```

You should see a JSON response with workout details!

## 🔧 Manual Setup (if make doesn't work)

If the `make setup` command doesn't work, do this manually:

```bash
# 1. Create virtual environment
python3.11 -m venv .venv

# 2. Activate it
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install packages
pip install -r requirements.txt

# 4. Copy environment file
cp .env.example .env

# 5. Edit .env with your API key
nano .env

# 6. Run the app
python main.py
```

## 🌐 Deploy to the Internet (Optional)

Want to put your API online so others can use it? Here's how:

### What You Need
- **Google Cloud account** (free tier works)
- **Credit card** (for verification, won't charge you)

### Step 1: Setup Google Cloud
```bash
# Install Google Cloud CLI
# Download from: https://cloud.google.com/sdk/docs/install

# Login to Google
gcloud auth login

# Set up the project
make setup-gcp
```

### Step 2: Store Your API Key Securely
```bash
# This stores your API key safely in Google Cloud
make create-secrets
```

### Step 3: Deploy!
```bash
# Deploy to the internet
make deploy

# Your API will be live at a URL like:
# https://tiktok-workout-parser-123456789.us-central1.run.app
```

### Automatic Deployments (Optional)
This project includes GitHub Actions for automatic deployments:

1. **Push to `main` branch** → Deploys to production
2. **Push to `staging` branch** → Deploys to staging
3. **Pull requests** → Runs tests only

To enable automatic deployments:
1. Set up GitHub repository secrets:
   - `WIF_PROVIDER`: Google Cloud Workload Identity Provider
   - `WIF_SERVICE_ACCOUNT`: Service account email
2. Push to `main` or `staging` branches

## 🛠️ Development Commands

Once you have it running, here are some useful commands:

```bash
# Start development server (auto-reloads when you change code)
make dev

# Run tests
make test

# Check code quality
make validate

# Format your code
make format

# See all available commands
make help
```

## 📚 API Reference

### Endpoints

#### `GET /health`
Check if the API is working.
```bash
curl http://localhost:8080/health
```
**Response:**
```json
{"status": "healthy", "timestamp": "2024-01-01T12:00:00", "environment": "development"}
```

#### `POST /process`
Process a TikTok video and get workout data.
```bash
curl -X POST http://localhost:8080/process \
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
          "rest_seconds": 30
        }
      ],
      "instructions": "Start standing, drop to plank, do push-up, jump back up"
    }
  ],
  "tags": ["hiit", "cardio", "fullbody"],
  "creator": "@fitnessuser"
}
```

### Error Responses

| Status | Meaning | What to do |
|--------|---------|------------|
| 400 | Bad URL | Check your TikTok URL |
| 404 | Video not found | Video might be private or deleted |
| 422 | Can't parse workout | Try a different workout video |
| 429 | Too many requests | Wait a few minutes and try again |
| 500 | Server error | Check if your API key is correct |



## 🔧 Making Changes

Want to modify the code? Here's how:

### Project Structure
```
sets-ai-backend/
├── main.py                 # Main API file
├── requirements.txt        # Python packages
├── src/
│   ├── services/
│   │   ├── genai_service.py    # AI analysis
│   │   └── tiktok_scraper.py   # Video downloading
│   └── worker/
│       └── video_processor.py  # Video processing
└── README.md
```

### Common Changes

#### Add a New API Endpoint
```python
# In main.py
@app.get("/new-endpoint")
async def new_endpoint():
    return {"message": "Hello!"}
```

#### Change the AI Prompt
```python
# In src/services/genai_service.py
# Find the prompt variable and modify it
```

#### Add New Dependencies
```bash
# Add to requirements.txt
echo "new-package==1.0.0" >> requirements.txt

# Install
make install
```

### Development Workflow
```bash
# 1. Make your changes
nano main.py  # or use any editor

# 2. Test locally
make dev

# 3. Run tests
make test

# 4. Deploy
make deploy
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
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'
```

#### Production Testing
```bash
# Test the live API
curl -X GET "https://tiktok-workout-parser-341666880405.us-central1.run.app/health"

# Test video processing
curl -X POST "https://tiktok-workout-parser-341666880405.us-central1.run.app/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'
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

This project follows security best practices:

- ✅ **API keys stored securely** in Google Secret Manager
- ✅ **HTTPS only** - all connections are encrypted
- ✅ **No data storage** - we don't save your videos or data
- ✅ **Input validation** - all URLs are checked before processing
- ✅ **Error handling** - safe error messages, no sensitive data exposed

## 💰 Cost Information

### Google Cloud Pricing (Free Tier)
- **2 million requests/month** - FREE
- **After free tier** - ~$0.40 per million requests
- **Compute time** - ~$0.00002400 per 100ms

### Estimated Monthly Costs
- **Low usage** (< 1000 requests): $0-5/month
- **Medium usage** (10,000 requests): $5-20/month
- **High usage** (100,000 requests): $20-100/month

*Note: Most users stay within the free tier!*

## 🐛 Troubleshooting

### Common Problems

#### "API key not found" error
```bash
# Make sure you added your API key to .env
nano .env
# Check this line: SCRAPECREATORS_API_KEY=your_actual_key_here
```

#### "Python not found" error
```bash
# Install Python 3.11 from python.org
# Or use pyenv: pyenv install 3.11.0
```

#### "make command not found" error
```bash
# On Windows: Install Make from chocolatey or use the manual setup
# On Mac: Install Xcode command line tools
# On Linux: sudo apt-get install make
```

#### "Permission denied" error
```bash
# Make sure you're in the right directory
pwd  # Should show /path/to/sets-ai-backend
ls   # Should show main.py, requirements.txt, etc.
```

#### App won't start
```bash
# Check if port 8080 is already in use
lsof -i :8080
# Kill the process or use a different port
```

### Getting Help

1. **Check the logs** when running `make dev`
2. **Make sure your API key is correct** in the `.env` file
3. **Try the manual setup** if `make setup` doesn't work
4. **Open an issue** on GitHub if you're still stuck

## 📈 Performance

- **Average time**: 2-3 minutes per video
- **Video download**: ~30 seconds
- **AI analysis**: ~1-2 minutes
- **Memory usage**: 2GB
- **Timeout**: 15 minutes max

## 📝 Additional Resources

### Useful Commands
```bash
make help         # Show all available commands
make setup        # Initial project setup
make run          # Run locally
make deploy       # Deploy to production
make logs         # View logs
make clean        # Clean temporary files
```

### Environment Management
- **Development**: Local testing with hot reload
- **Staging**: Pre-production testing with isolated resources  
- **Production**: Live service with monitoring and scaling

### Monitoring
- Cloud Run metrics in Google Cloud Console
- Structured logs with request tracking
- Health endpoint for uptime monitoring
- Performance headers (X-Process-Time)

## 🤝 Contributing

1. Follow the development workflow above
2. Ensure all tests pass (`make validate`)
3. Update documentation as needed
4. Create pull request with clear description

## ❓ FAQ

### "What types of videos work best?"
- **Workout videos** with clear exercises
- **Videos with audio** (we extract the transcript)
- **Public TikTok videos** (not private)

### "How accurate is the AI?"
- **Very good** for standard exercises (push-ups, squats, etc.)
- **Good** for common workout types (HIIT, strength, cardio)
- **May struggle** with very unique or complex movements

### "Can I use this commercially?"
- **Yes!** This is open source
- **Check ScrapeCreators terms** for their API usage
- **Google Cloud costs** apply for hosting

### "What if the API is slow?"
- **Normal**: 2-3 minutes is expected
- **Check your internet** connection
- **Try a different video** if it's taking too long

---

**How it works:**
1. Downloads TikTok video using ScrapCreators API (no watermark)
2. Extracts transcript directly from video info response (single API call)
3. Removes audio from video using ffmpeg
4. Analyzes silent video + transcript with Gemini 2.0 Flash
5. Returns structured workout JSON
