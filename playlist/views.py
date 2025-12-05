from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import random
import string

from .models import Movie, Playlist, PlaylistItem
from .serializers import (
    MovieSerializer,
    PlaylistSerializer,
    PlaylistListSerializer,
    PlaylistItemSerializer,
    AddMovieToPlaylistSerializer,
    UpdatePlaylistItemStatusSerializer,
    UserRegistrationSerializer,
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

class RegisterView(APIView):
    """
    User registration endpoint.
    POST /api/auth/register/ - Register a new user and return token
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Create token for the new user
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
    """
    User login endpoint.
    POST /api/auth/login/ - Login and get token
    """
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Try case-insensitive username lookup
        try:
            user = User.objects.get(username__iexact=username)
            # Authenticate with the actual username from database
            authenticated_user = authenticate(username=user.username, password=password)
            
            if authenticated_user:
                # Get or create token for the user
                token, created = Token.objects.get_or_create(user=authenticated_user)
                
                # Return response in the format your frontend expects
                return Response({
                    'access': token.key,
                    'refresh': '',  # Add if you implement refresh tokens
                    'user_id': authenticated_user.id,
                    'username': authenticated_user.username,
                    'email': authenticated_user.email,
                    'message': 'Login successful'
                }, status=status.HTTP_200_OK)
            else:
                # User exists but password is wrong
                return Response(
                    {'error': 'Invalid password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        except User.DoesNotExist:
            # User doesn't exist
            return Response(
                {'error': 'User does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )


class TMDBSearchView(APIView):
    """
    Proxy endpoint for TMDB search.
    GET /api/tmdb/search/?query=<movie_name>&page=1
    """
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
    """
    Proxy endpoint for TMDB movie details.
    GET /api/tmdb/movies/<tmdb_id>/
    """
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
    """Proxy endpoint for TMDB TV show details (with seasons list)."""
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
    """Proxy endpoint for TMDB TV season (episodes list)."""
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


class MovieViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Movie CRUD operations.
    
    GET /api/movies/ - List all movies
    POST /api/movies/ - Create a movie
    GET /api/movies/{id}/ - Get movie detail
    PUT /api/movies/{id}/ - Update movie
    DELETE /api/movies/{id}/ - Delete movie
    POST /api/movies/get_or_create/ - Get or create movie from TMDB
    """
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"])
    def get_or_create(self, request):
        """
        Get or create a movie from TMDB ID.
        If movie exists locally, return it.
        If not, fetch from TMDB, create locally, and return.
        """
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
    
    GET /api/playlists/ - List all user playlists (requires auth)
    POST /api/playlists/ - Create a playlist (requires auth)
    GET /api/playlists/{id}/ - Get playlist detail with movies (requires auth)
    PUT /api/playlists/{id}/ - Update playlist (requires auth)
    DELETE /api/playlists/{id}/ - Delete playlist (requires auth)
    
    Custom Actions:
    POST /api/playlists/{id}/add_movie/ - Add a movie to playlist
    DELETE /api/playlists/{id}/remove_movie/ - Remove a movie from playlist
    PATCH /api/playlists/{id}/update_item_status/ - Update movie status in playlist
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

        # Check if already in playlist
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
        
        # Automatically organize into status playlists based on watch status
        # This only affects the 3 system playlists, not user's custom playlists
        self.move_to_status_playlist(playlist.user, movie, status_value)
        
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
        
        item.status = new_status
        item.save()
        
        # Auto-move to corresponding status playlist
        if new_status:  # If status is set (not empty)
            self.move_to_status_playlist(playlist.user, item.movie, new_status)

        return Response(PlaylistItemSerializer(item).data)
    
    def move_to_status_playlist(self, user, movie, status):
        """Move movie to the corresponding status playlist"""
        status_playlist_map = {
            'watched': 'Watched',
            'watching': 'Watching',
            'to_watch': 'To Watch'
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
        
        # Remove from all other status playlists
        status_playlists = Playlist.objects.filter(
            user=user,
            title__in=['Watched', 'Watching', 'To Watch']
        ).exclude(id=target_playlist.id)
        
        for pl in status_playlists:
            PlaylistItem.objects.filter(playlist=pl, movie=movie).delete()
        
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
        item = get_object_or_404(PlaylistItem, playlist=playlist, movie_id=movie_id)

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


class RequestPasswordResetView(APIView):
    """
    Request password reset code.
    POST /api/auth/password-reset/request/ - Send verification code to email
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        
        if not email:
            return Response(
                {'error': 'Email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'No account found with this email address'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate verification code
        code = generate_verification_code()
        
        # Store code in cache with 10-minute expiration
        cache_key = f'password_reset_{user.id}'
        cache.set(cache_key, code, settings.PASSWORD_RESET_TIMEOUT)
        
        # Check if email is configured
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            # For development: return code in response (REMOVE IN PRODUCTION!)
            return Response({
                'message': 'Email not configured. Development mode: code shown in response',
                'user_id': user.id,
                'dev_code': code,  # Only for development!
                'warning': 'Configure EMAIL_HOST_USER and EMAIL_HOST_PASSWORD environment variables'
            }, status=status.HTTP_200_OK)
        
        # Send email
        try:
            subject = 'TrackR - Password Reset Code'
            message = f"""
Hello {user.username},

You requested to reset your password for your TrackR account.

Your verification code is: {code}

This code will expire in 10 minutes.

If you didn't request this, please ignore this email.

Best regards,
TrackR Team
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            return Response({
                'message': 'Verification code sent to your email',
                'user_id': user.id
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Log the error for debugging
            import traceback
            print(f"Email sending error: {str(e)}")
            print(traceback.format_exc())
            
            return Response(
                {'error': f'Failed to send email. Please check server email configuration. Error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyResetCodeView(APIView):
    """
    Verify password reset code.
    POST /api/auth/password-reset/verify/ - Verify the code
    """
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
        
        # Mark code as verified (store with different key)
        verified_key = f'password_reset_verified_{user_id}'
        cache.set(verified_key, True, 600)  # 10 minutes to complete reset
        
        return Response({
            'message': 'Code verified successfully'
        }, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """
    Reset password after verification.
    POST /api/auth/password-reset/confirm/ - Set new password
    """
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


class RequestChangePasswordCodeView(APIView):
    """
    Request verification code for changing password (authenticated users).
    POST /api/auth/change-password/request/ - Send code to user's email
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        
        if not user.email:
            return Response(
                {'error': 'No email address associated with your account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate verification code
        code = generate_verification_code()
        
        # Store code in cache
        cache_key = f'change_password_{user.id}'
        cache.set(cache_key, code, settings.PASSWORD_RESET_TIMEOUT)
        
        # Check if email is configured
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            # For development: return code in response (REMOVE IN PRODUCTION!)
            return Response({
                'message': 'Email not configured. Development mode: code shown in response',
                'email': user.email,
                'dev_code': code,  # Only for development!
                'warning': 'Configure EMAIL_HOST_USER and EMAIL_HOST_PASSWORD environment variables'
            }, status=status.HTTP_200_OK)
        
        # Send email
        try:
            subject = 'TrackR - Change Password Verification Code'
            message = f"""
Hello {user.username},

You requested to change your password for your TrackR account.

Your verification code is: {code}

This code will expire in 10 minutes.

If you didn't request this, please secure your account immediately.

Best regards,
TrackR Team
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            return Response({
                'message': 'Verification code sent to your email',
                'email': user.email
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Log the error for debugging
            import traceback
            print(f"Email sending error: {str(e)}")
            print(traceback.format_exc())
            
            return Response(
                {'error': f'Failed to send email. Please check server email configuration. Error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChangePasswordView(APIView):
    """
    Change password with verification code (authenticated users).
    POST /api/auth/change-password/ - Change password
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
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
        
        # Regenerate token for security
        Token.objects.filter(user=user).delete()
        new_token = Token.objects.create(user=user)
        
        return Response({
            'message': 'Password changed successfully',
            'access': new_token.key
        }, status=status.HTTP_200_OK)

