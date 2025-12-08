#!/usr/bin/env python
"""
Database fix script for EpisodeProgress issues.
Run this before migrations on Render.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CineStack.settings')
django.setup()

from playlist.models import EpisodeProgress, Movie
from django.db import transaction
from django.db.models import Count
from django.contrib.auth import get_user_model

User = get_user_model()

def fix_database_issues():
    """Fix duplicate and invalid foreign key issues."""
    print("=" * 60)
    print("DATABASE CLEANUP SCRIPT")
    print("=" * 60)
    
    # Count before
    total_users = User.objects.count()
    total_movies = Movie.objects.count()
    total_episodes = EpisodeProgress.objects.count()
    
    print(f"\n📊 BEFORE CLEANUP:")
    print(f"  Users: {total_users}")
    print(f"  Movies: {total_movies}")
    print(f"  EpisodeProgress: {total_episodes}")
    
    # FIX 1: Delete rows with invalid series_id
    print("\n🔧 STEP 1: Checking invalid series_id references...")
    
    valid_series_ids = set(Movie.objects.values_list('id', flat=True))
    invalid_progress = EpisodeProgress.objects.exclude(series_id__in=valid_series_ids)
    
    if invalid_progress.exists():
        print(f"  Found {invalid_progress.count()} invalid rows")
        print("  Deleting invalid rows...")
        invalid_count = invalid_progress.count()
        invalid_progress.delete()
        print(f"  ✅ Deleted {invalid_count} rows")
    else:
        print("  ✅ No invalid series_id references found")
    
    # FIX 2: Remove duplicate EpisodeProgress entries
    print("\n🔧 STEP 2: Checking for duplicates...")
    
    # Find duplicate combinations
    duplicates = EpisodeProgress.objects.values(
        'user_id', 'series_id', 'season', 'episode'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')
    
    if duplicates.exists():
        print(f"  Found {duplicates.count()} duplicate groups")
        total_deleted = 0
        
        for dup in duplicates:
            # Get all duplicates for this combination
            dup_rows = EpisodeProgress.objects.filter(
                user_id=dup['user_id'],
                series_id=dup['series_id'],
                season=dup['season'],
                episode=dup['episode']
            ).order_by('-updated_at')  # Keep most recent
            
            # Keep the most recent one, delete older ones
            keep = dup_rows.first()
            to_delete = dup_rows.exclude(id=keep.id)
            
            if to_delete.exists():
                deleted_count = to_delete.count()
                total_deleted += deleted_count
                print(f"    - Keeping ID {keep.id} (most recent), deleting {deleted_count} older")
                to_delete.delete()
        
        print(f"  ✅ Deleted {total_deleted} duplicate rows total")
    else:
        print("  ✅ No duplicates found")
    
    # Count after
    remaining_episodes = EpisodeProgress.objects.count()
    deleted_total = total_episodes - remaining_episodes
    
    print("\n📊 AFTER CLEANUP:")
    print(f"  EpisodeProgress: {remaining_episodes}")
    print(f"  Total deleted: {deleted_total}")
    print("\n✅ DATABASE CLEANUP COMPLETE!")
    
    # Verify fixes
    print("\n🔍 VERIFICATION:")
    
    # Check for remaining invalid references
    remaining_invalid = EpisodeProgress.objects.exclude(
        series_id__in=Movie.objects.values_list('id', flat=True)
    ).exists()
    
    if not remaining_invalid:
        print("  ✅ No invalid foreign keys remaining")
    else:
        print("  ❌ Still have invalid foreign keys")
        return False
    
    # Check for remaining duplicates
    remaining_dups = EpisodeProgress.objects.values(
        'user_id', 'series_id', 'season', 'episode'
    ).annotate(count=Count('id')).filter(count__gt=1).exists()
    
    if not remaining_dups:
        print("  ✅ No duplicates remaining")
    else:
        print("  ❌ Still have duplicates")
        return False
    
    return True

if __name__ == "__main__":
    print("\n🚀 Starting database fix...")
    
    try:
        # Run in transaction
        with transaction.atomic():
            success = fix_database_issues()
            
            if success:
                print("\n🎉 ALL ISSUES FIXED SUCCESSFULLY!")
                print("You can now run: python manage.py migrate")
                sys.exit(0)
            else:
                print("\n⚠️ Some issues remain. Manual cleanup may be needed.")
                sys.exit(1)
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
