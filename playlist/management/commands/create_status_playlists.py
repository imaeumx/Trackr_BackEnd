"""
Management command to create automatic status playlists for all existing users.
Usage: python manage.py create_status_playlists
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from playlist.models import Playlist


class Command(BaseCommand):
    help = 'Create automatic status playlists (Watched, Watching, To Watch) for all users'

    def handle(self, *args, **options):
        users = User.objects.all()
        created_count = 0
        
        status_playlists = [
            {
                'title': 'Watched',
                'description': 'Movies and series I have watched'
            },
            {
                'title': 'Watching',
                'description': 'Movies and series I am currently watching'
            },
            {
                'title': 'To Watch',
                'description': 'Movies and series I want to watch'
            }
        ]
        
        for user in users:
            for pl_data in status_playlists:
                playlist, created = Playlist.objects.get_or_create(
                    user=user,
                    title=pl_data['title'],
                    defaults={
                        'description': pl_data['description'],
                        'is_status_playlist': True
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Created "{pl_data["title"]}" playlist for user "{user.username}"'
                        )
                    )
                elif not playlist.is_status_playlist:
                    # Update existing playlists that aren't marked as status playlists
                    playlist.is_status_playlist = True
                    playlist.save()

        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nTotal playlists created: {created_count}'
            )
        )
