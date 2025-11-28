from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MovieViewSet,
    PlaylistViewSet,
    PlaylistItemViewSet,
    TMDBSearchView,
    TMDBMovieDetailView,
    TMDBTVDetailView,
    TMDBTVSeasonDetailView,
    TMDBPopularView,
)

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r"movies", MovieViewSet, basename="movie")
router.register(r"playlists", PlaylistViewSet, basename="playlist")
router.register(r"playlist-items", PlaylistItemViewSet, basename="playlistitem")

# The API URLs are now determined automatically by the router
urlpatterns = [
    path("", include(router.urls)),
    # TMDB proxy endpoints
    path("tmdb/search/", TMDBSearchView.as_view(), name="tmdb-search"),
    path("tmdb/movies/<int:tmdb_id>/", TMDBMovieDetailView.as_view(), name="tmdb-movie-detail"),
    path("tmdb/tv/<int:tmdb_id>/", TMDBTVDetailView.as_view(), name="tmdb-tv-detail"),
    path(
        "tmdb/tv/<int:tmdb_id>/seasons/<int:season_number>/",
        TMDBTVSeasonDetailView.as_view(),
        name="tmdb-tv-season-detail",
    ),
    path("tmdb/popular/", TMDBPopularView.as_view(), name="tmdb-popular"),
]
