# Generated migration to clean up orphaned playlists and make user field required

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def delete_orphaned_playlists(apps, schema_editor):
    """Delete any playlists that don't have a user assigned."""
    Playlist = apps.get_model('playlist', 'Playlist')
    Playlist.objects.filter(user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('playlist', '0005_playlist_user_playlist_unique_playlist_per_user'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # First, delete orphaned playlists
        migrations.RunPython(delete_orphaned_playlists),
        
        # Then, alter the field to make user required (not null, not blank)
        migrations.AlterField(
            model_name='playlist',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='playlists',
                to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
