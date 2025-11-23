#!/bin/bash
# Build script for Render deployment

set -e  # Exit on error

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# MediaPipe might need additional setup
echo "Verifying MediaPipe installation..."
python -c "import mediapipe; print('MediaPipe installed successfully')" || {
    echo "MediaPipe installation failed, trying alternative method..."
    pip install --upgrade setuptools wheel
    pip install mediapipe --no-cache-dir
}

echo "Build complete!"

