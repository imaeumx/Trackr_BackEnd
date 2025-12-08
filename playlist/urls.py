from .views import simple_change_password_request, simple_change_password
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MovieViewSet,
    PlaylistViewSet,
    PlaylistItemViewSet,
    FavoriteViewSet,
    ReviewViewSet,
    EpisodeProgressViewSet,
    TMDBSearchView,
    TMDBMovieDetailView,
    TMDBTVDetailView,
    TMDBTVSeasonDetailView,
    TMDBPopularView,
    TMDBTopRatedView,
    get_playlist_items,
    RequestPasswordResetView,
    VerifyResetCodeView,  # ADD THIS IMPORT!
    ResetPasswordView,
    LoginView,
    RegisterView
)


# Create a router and register our viewsets
router = DefaultRouter()
router.register(r"movies", MovieViewSet, basename="movie")
router.register(r"playlists", PlaylistViewSet, basename="playlist")
router.register(r"playlist-items", PlaylistItemViewSet, basename="playlistitem")
router.register(r"favorites", FavoriteViewSet, basename="favorite")
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"episode-progress", EpisodeProgressViewSet, basename="episodeprogress")

# The API URLs are now determined automatically by the router
urlpatterns = [
    path("", include(router.urls)),
    # Playlist items endpoint
    path("playlists/<int:playlist_id>/items/", get_playlist_items, name="playlist-items"),
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
    path("tmdb/top-rated/", TMDBTopRatedView.as_view(), name="tmdb-top-rated"),
    # Password reset endpoints
    path("auth/password-reset/request/", RequestPasswordResetView.as_view(), name="password-reset-request"),
    path("auth/password-reset/verify/", VerifyResetCodeView.as_view(), name="password-reset-verify"),  # ADD THIS LINE!
    path("auth/password-reset/confirm/", ResetPasswordView.as_view(), name="password-reset-confirm"),
    # USE SIMPLE CHANGE PASSWORD ENDPOINTS ONLY
    path("auth/change-password/request/", simple_change_password_request, name="change-password-request"),
    path("auth/change-password/", simple_change_password, name="change-password"),
    # Auth endpoints
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/register/', RegisterView.as_view(), name='register'),
]