#!/usr/bin/env bash
# Render Build Script - FINAL

echo "🚀 Starting Render build..."
echo "=========================="

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

echo "✅ Build complete!"
echo "=========================="