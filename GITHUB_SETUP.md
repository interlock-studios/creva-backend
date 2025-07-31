# GitHub Actions Setup Guide

## Quick Setup for Automatic Deployments

### 1. Get Your Google Cloud Service Account Key

```bash
# Create a service account key (if you don't have one)
gcloud iam service-accounts keys create ~/service-account-key.json \
  --iam-account=tiktok-workout-parser@sets-ai.iam.gserviceaccount.com
```

### 2. Add the Secret to GitHub

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `GOOGLE_CLOUD_CREDENTIALS`
5. Value: Copy the entire contents of `~/service-account-key.json`

### 3. That's It!

Now when you push to:
- `main` branch → Deploys to production
- `staging` branch → Deploys to staging
- Any other branch → Runs tests only

### What the Workflow Does

1. **Tests**: Runs `make validate` to check code quality
2. **Deploys**: Runs `make deploy` (or `./deploy.sh`) automatically
3. **Reports**: Shows deployment URL in the logs

### Troubleshooting

- **"Permission denied"**: Make sure your service account has the right permissions
- **"Secret not found"**: Check that `GOOGLE_CLOUD_CREDENTIALS` is set correctly
- **"Deploy failed"**: Check the logs for specific error messages

The workflow is intentionally simple - it just runs the same commands you'd run locally! 