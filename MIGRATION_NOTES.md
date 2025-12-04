# Database Migration Instructions

## Fix for Orphaned Playlists Issue

New users were seeing existing playlists because some playlists were created without a user assigned (orphaned playlists).

### Changes Made:
1. Created migration `0006_cleanup_orphaned_playlists_and_make_user_required.py`
   - This automatically deletes any playlists that don't have a user assigned
   - Makes the `user` field required on the Playlist model (no more null/blank)

2. Updated `views.py` to add extra safety filter

3. Updated `models.py` to make user field required

### To Apply the Migration:

```bash
cd Trackr_BackEnd
python manage.py migrate
```

This will:
1. Delete all orphaned playlists (ones without a user)
2. Update the Playlist model to require a user

### Result:
- New users will start with 0 playlists (no inherited/orphaned playlists)
- All new playlists must be assigned to the creating user
- Old orphaned playlists will be cleaned up automatically

No manual database cleanup needed!
