# Deploying to Google Cloud Run

Google Cloud Run supports MediaPipe and ResNet50 with flexible memory options.

## Prerequisites:
- Google Cloud account (free $300 credit)
- `gcloud` CLI installed

## Steps:

1. **Create a Dockerfile**:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
```

2. **Build and Deploy**:
```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Build container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/xai-morphing-studio

# Deploy to Cloud Run
gcloud run deploy xai-morphing-studio \
  --image gcr.io/YOUR_PROJECT_ID/xai-morphing-studio \
  --platform managed \
  --region us-central1 \
  --memory 4Gi \
  --timeout 300 \
  --allow-unauthenticated
```

## Advantages:
- ✅ Flexible memory (up to 8GB)
- ✅ Pay per use (only when running)
- ✅ MediaPipe works perfectly
- ✅ Auto-scaling

## Pricing:
- Free tier: 2 million requests/month
- After: ~$0.40 per million requests + compute time

