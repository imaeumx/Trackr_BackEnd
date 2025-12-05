from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone


class Movie(models.Model):
    """Movie model - stores movie info (can be manually added or fetched from TMDB)."""

    class MediaType(models.TextChoices):
        MOVIE = "movie", "Movie"
        TV = "tv", "TV Show"

    title = models.CharField(max_length=512)
    poster_url = models.URLField(max_length=1024, blank=True, null=True)
    description = models.TextField(blank=True, default="")
    release_year = models.PositiveIntegerField(blank=True, null=True)
    media_type = models.CharField(
        max_length=16,
        choices=MediaType.choices,
        default=MediaType.MOVIE,
    )
    # TMDB integration fields
    tmdb_id = models.IntegerField(blank=True, null=True, db_index=True)
    youtube_id = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["tmdb_id", "media_type"],
                name="playlist_movie_unique_tmdb_media_type",
                condition=~Q(tmdb_id__isnull=True),
            )
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.release_year or 'N/A'})"


class Playlist(models.Model):
    """Playlist/Watchlist - core CRUD entity for the mobile app."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='playlists'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    is_status_playlist = models.BooleanField(
        default=False,
        help_text="True for automatic Watched/Watching/To Watch playlists"
    )
    movies = models.ManyToManyField(
        Movie,
        through="PlaylistItem",
        related_name="playlists",
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'title'],
                name='unique_playlist_per_user'
            )
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def movie_count(self) -> int:
        return self.items.count()

    @property
    def watched_count(self) -> int:
        return self.items.filter(status=PlaylistItem.Status.WATCHED).count()

    def get_progress(self):
        """Returns (watched, total) tuple for progress tracking."""
        total = self.items.count()
        watched = self.items.filter(status=PlaylistItem.Status.WATCHED).count()
        return watched, total


class PlaylistItem(models.Model):
    """Through model linking Movie <-> Playlist with watch status."""

    class Status(models.TextChoices):
        TO_WATCH = "to_watch", "To Watch"
        WATCHING = "watching", "Watching"
        WATCHED = "watched", "Watched"

    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="items"
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="playlist_items"
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.TO_WATCH
    )
    user_rating = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        help_text="User rating from 1-5 stars"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("playlist", "movie")
        ordering = ["-added_at"]

    def __str__(self) -> str:
        return f"{self.movie.title} in {self.playlist.title} ({self.get_status_display()})"

