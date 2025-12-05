"""
Django signals for the playlist app.
Signals are used to handle automatic tasks when models are created/updated.
"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Playlist

# Add any signal handlers here
# For example, create default playlists when a user is created
# @receiver(post_save, sender=User)
# def create_default_playlists(sender, instance, created, **kwargs):
#     if created:
#         # Create default playlists for new users
#         pass
