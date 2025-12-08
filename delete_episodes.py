#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CineStack.settings')
django.setup()

from django.db import connection

print("Deleting ALL EpisodeProgress data...")

with connection.cursor() as cursor:
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlist_episodeprogress'")
    if cursor.fetchone():
        # Delete all data
        cursor.execute("DELETE FROM playlist_episodeprogress")
        print(f"Deleted {cursor.rowcount} rows")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM playlist_episodeprogress")
        count = cursor.fetchone()[0]
        print(f"Remaining rows: {count}")
        
        if count == 0:
            print("✅ Table is now empty")
        else:
            print("❌ Table still has data")
    else:
        print("Table doesn't exist yet")

print("Done!")
