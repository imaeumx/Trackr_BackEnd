from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone


# ...existing code...




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
        "Movie",
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
        DID_NOT_FINISH = "did_not_finish", "Did Not Finish"

    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="items"
    )
    movie = models.ForeignKey(
        "Movie",
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


class Favorite(models.Model):
    """User's favorite movies and TV shows."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorites'
    )
    movie = models.ForeignKey(
        "Movie",
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "movie")
        ordering = ["-added_at"]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.movie.title}"


class Review(models.Model):
    """User reviews and ratings for movies/shows."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.PositiveSmallIntegerField(
        help_text="Rating from 1-5 stars"
    )
    review_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "movie")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.movie.title} ({self.rating}/5)"


class EpisodeProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='episode_progress')
    series = models.ForeignKey('Movie', on_delete=models.CASCADE, related_name='episode_progress')
    season = models.PositiveIntegerField()
    episode = models.PositiveIntegerField()
    status = models.CharField(
        max_length=32,
        choices=[
            ('not_started', 'Not Started'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ],
        default='not_started',
    )
    notes = models.TextField(blank=True, default='')
    rating = models.PositiveSmallIntegerField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['series', 'season', 'episode']
        unique_together = ('user', 'series', 'season', 'episode')

    def __str__(self):
        return f"{self.user.username} - {self.series.title} S{self.season}E{self.episode}"

