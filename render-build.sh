#!/usr/bin/env bash
# Render Build Script

echo "🚀 Starting Render build process..."
echo "===================================="

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Clean up EpisodeProgress table if it exists (prevent migration errors)
echo "🔧 Checking for database issues..."
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CineStack.settings')
import django
django.setup()
from django.db import connection

try:
    with connection.cursor() as cursor:
        # Check if EpisodeProgress table exists
        cursor.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='playlist_episodeprogress')\")
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # Clean invalid foreign keys
            cursor.execute(\"DELETE FROM playlist_episodeprogress WHERE series_id NOT IN (SELECT id FROM playlist_movie)\")
            print(f'Deleted invalid foreign keys: {cursor.rowcount}')
            
            # Clean duplicates (PostgreSQL syntax)
            cursor.execute('''
                DELETE FROM playlist_episodeprogress 
                WHERE id NOT IN (
                    SELECT MIN(id) 
                    FROM playlist_episodeprogress 
                    GROUP BY user_id, series_id, season, episode
                )
            ''')
            print(f'Deleted duplicates: {cursor.rowcount}')
except Exception as e:
    print(f'Database check completed: {e}')
"

# Run migrations
echo "📝 Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Create default superuser if needed (optional)
# echo "👤 Creating default admin user..."
# python manage.py shell -c "
# from django.contrib.auth import get_user_model
# User = get_user_model()
# if not User.objects.filter(username='admin').exists():
#     User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
#     print('Default admin created')
# else:
#     print('Admin user already exists')
# "

echo "✅ Build process complete!"
echo "===================================="
