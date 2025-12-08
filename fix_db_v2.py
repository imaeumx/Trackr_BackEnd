#!/usr/bin/env python
"""
Database fix script v2 - More aggressive cleanup
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CineStack.settings')
django.setup()

from playlist.models import EpisodeProgress, Movie
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth import get_user_model

User = get_user_model()

def aggressive_cleanup():
    print("=" * 60)
    print("AGGRESSIVE DATABASE CLEANUP")
    print("=" * 60)
    
    # Get all valid movie IDs
    valid_movie_ids = list(Movie.objects.values_list('id', flat=True))
    print(f"Valid Movie IDs: {valid_movie_ids}")
    
    # STEP 1: Delete ALL EpisodeProgress with invalid series_id
    print("\n🗑️ STEP 1: Deleting ALL invalid references...")
    
    # Method 1: Delete where series_id not in valid movies
    invalid_count = EpisodeProgress.objects.exclude(series_id__in=valid_movie_ids).count()
    if invalid_count > 0:
        print(f"  Found {invalid_count} rows with invalid series_id")
        EpisodeProgress.objects.exclude(series_id__in=valid_movie_ids).delete()
        print(f"  ✅ Deleted {invalid_count} invalid rows")
    else:
        print("  ✅ No invalid references found")
    
    # STEP 2: Delete ALL duplicates (keep NONE, we'll recreate from scratch if needed)
    print("\n🗑️ STEP 2: Removing ALL EpisodeProgress data...")
    
    total_episodes = EpisodeProgress.objects.count()
    if total_episodes > 0:
        print(f"  Found {total_episodes} EpisodeProgress records")
        print("  Deleting ALL EpisodeProgress data...")
        EpisodeProgress.objects.all().delete()
        print(f"  ✅ Deleted all {total_episodes} records")
    else:
        print("  ✅ No EpisodeProgress records found")
    
    # STEP 3: Verify cleanup
    print("\n🔍 VERIFICATION:")
    
    remaining = EpisodeProgress.objects.count()
    if remaining == 0:
        print("  ✅ Database is clean - no EpisodeProgress records")
        return True
    else:
        print(f"  ❌ Still have {remaining} records")
        return False

if __name__ == "__main__":
    print("\n🚀 Starting aggressive database cleanup...")
    
    # Ask for confirmation
    print("\n⚠️ WARNING: This will DELETE ALL EpisodeProgress data!")
    print("This includes watched episodes, progress, etc.")
    response = input("Continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Aborted.")
        sys.exit(0)
    
    try:
        with transaction.atomic():
            success = aggressive_cleanup()
            
            if success:
                print("\n🎉 DATABASE CLEANED SUCCESSFULLY!")
                print("You can now run migrations without issues.")
                print("\nNote: EpisodeProgress data has been cleared.")
                print("Users will need to re-mark episodes as watched.")
                sys.exit(0)
            else:
                print("\n❌ Cleanup failed!")
                sys.exit(1)
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
