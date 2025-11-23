# Deploying to Railway

Railway is a great alternative to Render that supports MediaPipe and ResNet50 without modifications.

## Steps:

1. **Sign up at Railway**: https://railway.app
   - Connect your GitHub account

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `XAI_Morphing_Studio` repository

3. **Configure Service**:
   - Railway will auto-detect Python
   - Set **Start Command**: `gunicorn app:app`
   - Set **Memory**: At least 2GB (recommended: 4GB for ResNet50)

4. **Environment Variables** (optional):
   - `PORT`: Railway sets this automatically
   - `FLASK_ENV`: `production`

5. **Deploy**:
   - Railway will automatically build and deploy
   - First deployment takes ~10-15 minutes (PyTorch download)

## Railway Advantages:
- ✅ More memory options (up to 8GB)
- ✅ Better Python package support
- ✅ MediaPipe works out of the box
- ✅ Similar to Render (easy migration)
- ✅ Free tier available ($5 credit/month)

## Pricing:
- Free tier: $5 credit/month
- Paid: ~$5-20/month for 2-4GB memory

