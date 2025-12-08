import random
import string
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from django.db.models import Q
import os
from resend import Emails
from django.conf import settings
from django.utils import timezone

from .models import Movie, Playlist, PlaylistItem, Favorite, Review, EpisodeProgress
from .serializers import (
    MovieSerializer,
    PlaylistSerializer,
    PlaylistListSerializer,
    PlaylistItemSerializer,
    AddMovieToPlaylistSerializer,
    UpdatePlaylistItemStatusSerializer,
    UserRegistrationSerializer,
    FavoriteSerializer,
    ReviewSerializer,
    EpisodeProgressSerializer,
)
from .services import (
    search_tmdb,
    get_or_create_movie_from_tmdb,
    TMDBError,
    get_tmdb_tv_details,
    get_tmdb_tv_season_details,
    get_tmdb_popular,
    get_tmdb_top_rated,
)

User = get_user_model()

# ============ SIMPLE CHANGE PASSWORD ENDPOINTS ============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def simple_change_password_request(request):
    """Simple change password request - returns code in response"""
    user = request.user
    if not user.email:
        return Response(
            {'error': 'No email address associated with your account'},
            status=status.HTTP_400_BAD_REQUEST
        )
    code = ''.join(random.choices(string.digits, k=6))
    cache_key = f'change_password_{user.id}'
    cache.set(cache_key, code, 600)  # 10 minutes
    
    # Try to send email
    try:
        subject = 'TrackR - Change Password Verification Code'
        message = (
            f"Hello {user.username},\n\n"
            "You requested to change your password for your TrackR account.\n\n"
            f"Your verification code is: {code}\n\n"
            "This code will expire in 10 minutes.\n\n"
            "If you didn't request this, please secure your account immediately.\n\n"
            "Best regards,\nTrackR Team"
        )
        from_email = f"TrackR <{settings.DEFAULT_FROM_EMAIL}>"
        # FIX: Use dictionary format
        response = Emails.send({
            "from": from_email,
            "to": [user.email],
            "subject": subject,
            "text": message
        })
        email_sent = response.get('id') is not None
    except Exception as e:
        email_sent = False
        import traceback
        print(f"Email sending error: {str(e)}")
        print(traceback.format_exc())
    
    return Response({
        'message': 'Change password code generated',
        'email': user.email,
        'code': code,  # Return code for development
        'email_sent': email_sent,
        'user_id': user.id
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def simple_change_password(request):
    """Simple change password with code"""
    user = request.user
    code = request.data.get('code', '').strip()
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    
    if not code or not current_password or not new_password:
        return Response(
            {'error': 'Code, current password, and new password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify current password
    if not user.check_password(current_password):
        return Response(
            {'error': 'Current password is incorrect'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify code
    cache_key = f'change_password_{user.id}'
    stored_code = cache.get(cache_key)
    
    if not stored_code:
        return Response(
            {'error': 'Code expired or invalid. Please request a new one'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if stored_code != code:
        return Response(
            {'error': 'Invalid verification code'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(new_password) < 8:
        return Response(
            {'error': 'New password must be at least 8 characters long'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Change password
    user.set_password(new_password)
    user.save()
    
    # Clear cache
    cache.delete(cache_key)
    
    # Regenerate token
    Token.objects.filter(user=user).delete()
    new_token = Token.objects.create(user=user)
    
    return Response({
        'message': 'Password changed successfully',
        'access': new_token.key
    }, status=status.HTTP_200_OK)

# ============ HELPER FUNCTIONS ============

def generate_verification_code():
    """Generate a 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=6))

# ============ AUTH VIEWS ============

class RegisterView(APIView):
    """User registration endpoint."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            
            # Create automatic status playlists for new user
            self.create_status_playlists(user)
            
            return Response({
                'access': token.key,
                'user_id': user.id,
                'username': user.username,
                'message': 'Registration successful'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def create_status_playlists(self, user):
        """Create automatic status playlists for user"""
        status_playlists = [
            {'title': 'Watched', 'description': 'Movies and series I have watched'},
            {'title': 'Watching', 'description': 'Movies and series I am currently watching'},
            {'title': 'To Watch', 'description': 'Movies and series I want to watch'},
            {'title': 'Did Not Finish', 'description': 'Movies and series I stopped watching'}
        ]
        
        for pl_data in status_playlists:
            Playlist.objects.get_or_create(
                user=user,
                title=pl_data['title'],
                defaults={
                    'description': pl_data['description'],
                    'is_status_playlist': True
                }
            )

class LoginView(APIView):
    """User login endpoint."""
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(username__iexact=username)
            authenticated_user = authenticate(username=user.username, password=password)
            
            if authenticated_user:
                token, created = Token.objects.get_or_create(user=authenticated_user)
                
                return Response({
                    'access': token.key,
                    'refresh': '',
                    'user_id': authenticated_user.id,
                    'username': authenticated_user.username,
                    'email': authenticated_user.email,
                    'message': 'Login successful'
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Invalid password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        except User.DoesNotExist:
            return Response(
                {'error': 'User does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

# ============ PASSWORD RESET VIEWS ============

class RequestPasswordResetView(APIView):
    """Request password reset code."""
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = (
            request.data.get('email', '')
            or request.data.get('username', '')
            or request.data.get('login', '')
        ).strip()
        
        if not identifier:
            return Response(
                {'error': 'Email or username is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(
            Q(email__iexact=identifier) | Q(username__iexact=identifier)
        ).first()

        if not user:
            return Response(
                {'error': 'No account found with this email or username'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not user.email:
            return Response(
                {'error': 'No email address is associated with this account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        code = generate_verification_code()
        cache_key = f'password_reset_{user.id}'
        cache.set(cache_key, code, settings.PASSWORD_RESET_TIMEOUT)
        
        try:
            subject = 'TrackR - Password Reset Code'
            message = (
                f"Hello {user.username},\n\n"
                "You requested to reset your password for your TrackR account.\n\n"
                f"Your verification code is: {code}\n\n"
                "This code will expire in 10 minutes.\n\n"
                "If you didn't request this, please ignore this email.\n\n"
                "Best regards,\nTrackR Trio"
            )
            from_email = f"TrackR <{settings.DEFAULT_FROM_EMAIL}>"
            response = Emails.send(
                from_=from_email,
                to=[user.email],
                subject=subject,
                text=message
            )
            if response.get('id'):
                return Response({
                    'message': 'Verification code sent to your email',
                    'user_id': user.id
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Failed to send email.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            import traceback
            print(f"Email sending error: {str(e)}")
            print(traceback.format_exc())
            return Response(
                {'error': f'Failed to send email. Error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VerifyResetCodeView(APIView):
    """Verify password reset code."""
    permission_classes = [AllowAny]

    def post(self, request):
        user_id = request.data.get('user_id')
        code = request.data.get('code', '').strip()
        
        if not user_id or not code:
            return Response(
                {'error': 'User ID and code are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cache_key = f'password_reset_{user_id}'
        stored_code = cache.get(cache_key)
        
        if not stored_code:
            return Response(
                {'error': 'Code expired or invalid. Please request a new one'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if stored_code != code:
            return Response(
                {'error': 'Invalid verification code'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark code as verified
        verified_key = f'password_reset_verified_{user_id}'
        cache.set(verified_key, True, 600)
        
        return Response({
            'message': 'Code verified successfully'
        }, status=status.HTTP_200_OK)

class ResetPasswordView(APIView):
    """Reset password after verification."""
    permission_classes = [AllowAny]

    def post(self, request):
        user_id = request.data.get('user_id')
        new_password = request.data.get('new_password')
        
        if not user_id or not new_password:
            return Response(
                {'error': 'User ID and new password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(new_password) < 8:
            return Response(
                {'error': 'Password must be at least 8 characters long'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if code was verified
        verified_key = f'password_reset_verified_{user_id}'
        if not cache.get(verified_key):
            return Response(
                {'error': 'Please verify your code first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
            user.set_password(new_password)
            user.save()
            
            # Clear cache keys
            cache.delete(f'password_reset_{user_id}')
            cache.delete(verified_key)
            
            return Response({
                'message': 'Password reset successfully'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

# ============ TMDB VIEWS ============

class TMDBSearchView(APIView):
    """Proxy endpoint for TMDB search."""
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get('query', '')
        page = request.query_params.get('page', 1)
        media_type = request.query_params.get('type', 'multi')
        
        if not query:
            return Response(
                {'error': 'Query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            page = int(page)
        except ValueError:
            page = 1
        
        try:
            results = search_tmdb(query, page, media_type)
            return Response(results)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TMDBMovieDetailView(APIView):
    """Proxy endpoint for TMDB movie details."""
    permission_classes = [AllowAny]

    def get(self, request, tmdb_id):
        from .services import get_tmdb_movie_details
        
        try:
            details = get_tmdb_movie_details(tmdb_id)
            return Response(details)
        except TMDBError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TMDBTVDetailView(APIView):
    """Proxy endpoint for TMDB TV show details."""
    permission_classes = [AllowAny]

    def get(self, request, tmdb_id):
        try:
            details = get_tmdb_tv_details(tmdb_id)
            return Response(details)
        except TMDBError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TMDBTVSeasonDetailView(APIView):
    """Proxy endpoint for TMDB TV season."""
    permission_classes = [AllowAny]

    def get(self, request, tmdb_id, season_number):
        try:
            season_data = get_tmdb_tv_season_details(tmdb_id, season_number)
            return Response(season_data)
        except TMDBError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TMDBPopularView(APIView):
    """Proxy endpoint for TMDB popular movies/TV shows."""
    permission_classes = [AllowAny]

    def get(self, request):
        media_type = request.query_params.get("type", "movie")
        page = request.query_params.get("page", 1)

        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1

        try:
            results = get_tmdb_popular(media_type, page)
            return Response(results)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TMDBTopRatedView(APIView):
    """Proxy endpoint for TMDB top-rated movies/TV shows."""
    permission_classes = [AllowAny]

    def get(self, request):
        media_type = request.query_params.get("type", "movie")
        page = request.query_params.get("page", 1)

        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1

        try:
            results = get_tmdb_top_rated(media_type, page)
            return Response(results)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ============ MODEL VIEWSETS ============

class MovieViewSet(viewsets.ModelViewSet):
    """API endpoint for Movie CRUD operations."""
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"])
    def get_or_create(self, request):
        """Get or create a movie from TMDB ID."""
        tmdb_id = request.data.get('tmdb_id')
        media_type = request.data.get('media_type', Movie.MediaType.MOVIE)
        
        if not tmdb_id:
            return Response(
                {'error': 'tmdb_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            tmdb_id = int(tmdb_id)
        except ValueError:
            return Response(
                {'error': 'tmdb_id must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            movie, created = get_or_create_movie_from_tmdb(tmdb_id, media_type)
            serializer = MovieSerializer(movie)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )
        except TMDBError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PlaylistViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Playlist CRUD operations.
    """
    serializer_class = PlaylistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only current user's playlists - exclude any orphaned playlists and status playlists."""
        return Playlist.objects.filter(user=self.request.user, user__isnull=False)

    def perform_create(self, serializer):
        """Assign current user to new playlist."""
        serializer.save(user=self.request.user)

    def get_serializer_class(self):
        """Use lightweight serializer for list view, full serializer for detail."""
        if self.action == "list":
            return PlaylistListSerializer
        return PlaylistSerializer
    
    @action(detail=False, methods=["get"])
    def user_playlists(self, request):
        """Get only user-created playlists (exclude status playlists)."""
        user_playlists = Playlist.objects.filter(
            user=request.user,
            is_status_playlist=False
        )
        serializer = PlaylistListSerializer(user_playlists, many=True)
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a playlist - explicitly defined for clarity."""
        try:
            instance = self.get_object()
            playlist_title = instance.title
            self.perform_destroy(instance)
            return Response(
                {"message": f"Playlist '{playlist_title}' deleted successfully"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"])
    def add_movie(self, request, pk=None):
        """Add a movie to this playlist."""
        playlist = self.get_object()
        serializer = AddMovieToPlaylistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        movie_id = serializer.validated_data["movie_id"]
        status_value = serializer.validated_data["status"]

        movie = get_object_or_404(Movie, pk=movie_id)

        # If this is a status playlist, use move_to_status_playlist logic which handles all transitions
        if playlist.is_status_playlist:
            self.move_to_status_playlist(playlist.user, movie, status_value)
            # Return the item from the target status playlist
            target_status_name = {
                'watched': 'Watched',
                'watching': 'Watching',
                'to_watch': 'To Watch',
                'did_not_finish': 'Did Not Finish'
            }.get(status_value, 'To Watch')
            target_playlist = Playlist.objects.get(
                user=playlist.user,
                title=target_status_name,
                is_status_playlist=True
            )
            item = PlaylistItem.objects.get(playlist=target_playlist, movie=movie)
            return Response(
                PlaylistItemSerializer(item).data,
                status=status.HTTP_201_CREATED
            )
        
        # For non-status playlists, use standard add logic
        # Check if already in this specific playlist
        if PlaylistItem.objects.filter(playlist=playlist, movie=movie).exists():
            return Response(
                {"error": "Movie already in playlist"},
                status=status.HTTP_400_BAD_REQUEST
            )

        item = PlaylistItem.objects.create(
            playlist=playlist,
            movie=movie,
            status=status_value
        )
        
        # Update playlist's updated_at timestamp
        playlist.save()
        
        return Response(
            PlaylistItemSerializer(item).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["delete"], url_path="remove_movie/(?P<movie_id>[^/.]+)")
    def remove_movie(self, request, pk=None, movie_id=None):
        """Remove a movie from this playlist."""
        playlist = self.get_object()
        
        try:
            # Try to get the playlist item
            item = PlaylistItem.objects.get(playlist=playlist, movie_id=movie_id)
            item.delete()
            
            # Update playlist's updated_at timestamp
            playlist.save()
            
            return Response(
                {"message": f"Movie removed from playlist '{playlist.title}'"},
                status=status.HTTP_200_OK
            )
            
        except PlaylistItem.DoesNotExist:
            return Response(
                {"error": "Movie not found in this playlist"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["patch"], url_path="update_item_status/(?P<movie_id>[^/.]+)")
    def update_item_status(self, request, pk=None, movie_id=None):
        """Update a movie's watch status in this playlist and auto-move to status playlist."""
        playlist = self.get_object()
        item = get_object_or_404(PlaylistItem, playlist=playlist, movie_id=movie_id)

        serializer = UpdatePlaylistItemStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]
        old_status = item.status

        # Update status in all PlaylistItems for this user and movie
        PlaylistItem.objects.filter(
            movie_id=movie_id,
            playlist__user=playlist.user
        ).update(status=new_status)

        # Refresh item from DB
        item.refresh_from_db()

        # Auto-move to corresponding status playlist ONLY if this is a status playlist
        # Don't move movies when updating status in custom playlists
        if playlist.is_status_playlist and new_status:
            self.move_to_status_playlist(playlist.user, item.movie, new_status)

        return Response(PlaylistItemSerializer(item).data)
    
    def move_to_status_playlist(self, user, movie, status):
        """Move movie to the corresponding status playlist"""
        status_playlist_map = {
            'watched': 'Watched',
            'watching': 'Watching',
            'to_watch': 'To Watch',
            'did_not_finish': 'Did Not Finish'
        }
        
        if status not in status_playlist_map:
            return
        
        target_playlist_name = status_playlist_map[status]
        
        # Get or create the target status playlist
        target_playlist, created = Playlist.objects.get_or_create(
            user=user,
            title=target_playlist_name,
            defaults={
                'description': f'Movies and series I {status.replace("_", " ")}',
                'is_status_playlist': True
            }
        )
        
        # Ensure the playlist is marked as status playlist
        if not created and not target_playlist.is_status_playlist:
            target_playlist.is_status_playlist = True
            target_playlist.save()
        
        # Update status in all PlaylistItems (status and custom) for this user and movie
        PlaylistItem.objects.filter(
            movie=movie,
            playlist__user=user
        ).update(status=status)

        # Add to target status playlist (if not already there)
        item, created = PlaylistItem.objects.get_or_create(
            playlist=target_playlist,
            movie=movie,
            defaults={'status': status}
        )
        
        if not created:
            item.status = status
            item.save()

    @action(detail=True, methods=["patch"], url_path="update_item_rating/(?P<movie_id>[^/.]+)")
    def update_item_rating(self, request, pk=None, movie_id=None):
        """Update a movie's user rating in this playlist."""
        playlist = self.get_object()
        movie = get_object_or_404(Movie, pk=movie_id)
        item, created = PlaylistItem.objects.get_or_create(
            playlist=playlist,
            movie=movie,
            defaults={"status": PlaylistItem.Status.TO_WATCH}
        )

        rating = request.data.get('rating')
        if rating is None:
            return Response(
                {"error": "Rating is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return Response(
                    {"error": "Rating must be between 1 and 5"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid rating value"},
                status=status.HTTP_400_BAD_REQUEST
            )

        item.user_rating = rating
        item.save()

        return Response(PlaylistItemSerializer(item).data)


class PlaylistItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for PlaylistItem CRUD operations.
    Useful for directly managing items without going through playlist.
    
    GET /api/playlist-items/ - List all items
    GET /api/playlist-items/{id}/ - Get item detail
    PATCH /api/playlist-items/{id}/ - Update item (e.g., change status)
    DELETE /api/playlist-items/{id}/ - Remove item
    """
    queryset = PlaylistItem.objects.select_related("movie", "playlist").all()
    serializer_class = PlaylistItemSerializer


class EpisodeProgressViewSet(viewsets.ModelViewSet):
    """API endpoint for per-user episode progress.

    This viewset ensures users only see and modify their own episode progress records.
    """
    serializer_class = EpisodeProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return progress records for the requesting user
        qs = EpisodeProgress.objects.filter(user=self.request.user).select_related('series')

        # Optional filtering by series/season/episode via query params
        series_id = self.request.query_params.get('series')
        season = self.request.query_params.get('season')
        episode = self.request.query_params.get('episode')

        if series_id:
            try:
                qs = qs.filter(series_id=int(series_id))
            except (ValueError, TypeError):
                pass
        if season:
            try:
                qs = qs.filter(season=int(season))
            except (ValueError, TypeError):
                pass
        if episode:
            try:
                qs = qs.filter(episode=int(episode))
            except (ValueError, TypeError):
                pass

        return qs

    def perform_create(self, serializer):
        # Debug: log incoming data
        print('EpisodeProgressViewSet.perform_create:', serializer.validated_data)
        # Assign the current user on create
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        # Debug: log incoming data
        print('EpisodeProgressViewSet.perform_update:', serializer.validated_data)
        # Prevent changing ownership — always ensure user is request.user
        serializer.save(user=self.request.user)


@api_view(['GET'])
def get_playlist_items(request, playlist_id):
    """Get all items in a playlist."""
    playlist = get_object_or_404(Playlist, id=playlist_id)
    items = PlaylistItem.objects.filter(playlist=playlist).select_related('movie')
    serializer = PlaylistItemSerializer(items, many=True)
    return Response(serializer.data)


def generate_verification_code():
    """Generate a 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=6))


class FavoriteViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user favorites.
    GET /api/favorites/ - List all user favorites
    POST /api/favorites/ - Add to favorites (requires tmdb_id and media_type)
    DELETE /api/favorites/{id}/ - Remove from favorites by favorite ID
    """
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related('movie')

    def create(self, request, *args, **kwargs):
        """Add a movie/series to favorites."""
        tmdb_id = request.data.get('tmdb_id')
        media_type = request.data.get('media_type', 'movie')
        if not tmdb_id:
            return Response(
                {'error': 'tmdb_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            movie, created = get_or_create_movie_from_tmdb(tmdb_id, media_type)
            existing_favorite = Favorite.objects.filter(
                user=request.user,
                movie=movie
            ).first()
            if existing_favorite:
                serializer = self.get_serializer(existing_favorite)
                return Response(
                    {
                        'message': 'Already in favorites',
                        'favorite': serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            favorite = Favorite.objects.create(
                user=request.user,
                movie=movie
            )
            serializer = self.get_serializer(favorite)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except TMDBError as e:
            return Response(
                {'error': f'TMDB Error: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            print(f"[FavoriteViewSet] Error creating favorite: {str(e)}")
            print(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['delete'], url_path='remove_by_tmdb')
    def remove_by_tmdb(self, request):
        """Remove from favorites by TMDB ID."""
        tmdb_id = request.data.get('tmdb_id')

        if not tmdb_id:
            return Response(
                {'error': 'tmdb_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Find movie by TMDB ID
            movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
            if not movie:
                return Response(
                    {'error': 'Movie not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Delete the favorite
            deleted_count, _ = Favorite.objects.filter(
                user=request.user,
                movie=movie
            ).delete()

            if deleted_count == 0:
                return Response(
                    {'error': 'Favorite not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {'message': 'Removed from favorites'},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='check')
    def check_favorite(self, request):
        """Check if a movie/series is favorited."""
        tmdb_id = request.query_params.get('tmdb_id')

        if not tmdb_id:
            return Response(
                {'is_favorite': False},
                status=status.HTTP_200_OK
            )

        try:
            movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
            if not movie:
                return Response(
                    {'is_favorite': False},
                    status=status.HTTP_200_OK
                )

            is_favorite = Favorite.objects.filter(
                user=request.user,
                movie=movie
            ).exists()

            return Response(
                {'is_favorite': is_favorite},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {'is_favorite': False, 'error': str(e)},
                status=status.HTTP_200_OK
            )


class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user reviews.
    GET /api/reviews/ - List all user reviews
    POST /api/reviews/ - Add/Update review (requires tmdb_id, rating, optional review_text)
    DELETE /api/reviews/{id}/ - Delete review by review ID
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user).select_related('movie', 'user')

    def create(self, request, *args, **kwargs):
        """Add or update a review."""
        tmdb_id = request.data.get('tmdb_id')
        rating = request.data.get('rating')
        review_text = request.data.get('review_text', '')
        media_type = request.data.get('media_type', 'movie')

        if not tmdb_id:
            return Response(
                {'error': 'tmdb_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not rating or not (1 <= int(rating) <= 5):
            return Response(
                {'error': 'rating must be between 1 and 5'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get or create the movie from TMDB
            movie, _ = get_or_create_movie_from_tmdb(tmdb_id, media_type)
            
            # Create or update review
            review, created = Review.objects.update_or_create(
                user=request.user,
                movie=movie,
                defaults={
                    'rating': rating,
                    'review_text': review_text
                }
            )

            serializer = self.get_serializer(review)
            return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        except TMDBError as e:
            return Response(
                {'error': f'TMDB Error: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='by_movie')
    def get_review_by_movie(self, request):
        """Get user's review for a specific movie by TMDB ID."""
        tmdb_id = request.query_params.get('tmdb_id')

        if not tmdb_id:
            return Response(
                {'error': 'tmdb_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
            if not movie:
                return Response(None, status=status.HTTP_200_OK)

            review = Review.objects.filter(
                user=request.user,
                movie=movie
            ).first()

            if not review:
                return Response(None, status=status.HTTP_200_OK)

            serializer = self.get_serializer(review)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='my_reviews')
    def my_reviews(self, request):
        """Get all reviews by current user."""
        try:
            reviews = self.get_queryset()
            serializer = self.get_serializer(reviews, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['delete'], url_path='delete_by_movie')
    def delete_by_movie(self, request):
        """Delete user's review for a specific movie by TMDB ID or movie ID."""
        tmdb_id = request.data.get('tmdb_id')
        movie_id = request.data.get('movie_id')

        if not tmdb_id and not movie_id:
            return Response(
                {'error': 'tmdb_id or movie_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if tmdb_id:
                movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
            else:
                movie = Movie.objects.filter(id=movie_id).first()

            if not movie:
                return Response(
                    {'error': 'Movie not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            review = Review.objects.filter(
                user=request.user,
                movie=movie
            ).first()

            if not review:
                return Response(
                    {'error': 'Review not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            review.delete()
            return Response(
                {'message': 'Review deleted successfully'},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )