from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

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
            return Response({
                'access': token.key,
                'user_id': user.id,
                'username': user.username,
                'message': 'Registration successful'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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

        user = authenticate(username=username, password=password)
        
        if user:
            # Get or create token for the user
            token, created = Token.objects.get_or_create(user=user)
            
            # Return response in the format your frontend expects
            return Response({
                'access': token.key,
                'refresh': '',  # Add if you implement refresh tokens
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'message': 'Login successful'
            }, status=status.HTTP_200_OK)
        else:
            # Check if user exists to give better error message
            if User.objects.filter(username=username).exists():
                return Response(
                    {'error': 'Invalid password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            else:
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
    
    GET /api/playlists/ - List all playlists
    POST /api/playlists/ - Create a playlist
    GET /api/playlists/{id}/ - Get playlist detail with movies
    PUT /api/playlists/{id}/ - Update playlist
    DELETE /api/playlists/{id}/ - Delete playlist
    
    Custom Actions:
    POST /api/playlists/{id}/add_movie/ - Add a movie to playlist
    DELETE /api/playlists/{id}/remove_movie/ - Remove a movie from playlist
    PATCH /api/playlists/{id}/update_item_status/ - Update movie status in playlist
    """
    queryset = Playlist.objects.all()

    def get_serializer_class(self):
        """Use lightweight serializer for list view, full serializer for detail."""
        if self.action == "list":
            return PlaylistListSerializer
        return PlaylistSerializer

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
        return Response(
            PlaylistItemSerializer(item).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["delete"], url_path="remove_movie/(?P<movie_id>[^/.]+)")
    def remove_movie(self, request, pk=None, movie_id=None):
        """Remove a movie from this playlist."""
        playlist = self.get_object()
        item = get_object_or_404(PlaylistItem, playlist=playlist, movie_id=movie_id)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["patch"], url_path="update_item_status/(?P<movie_id>[^/.]+)")
    def update_item_status(self, request, pk=None, movie_id=None):
        """Update a movie's watch status in this playlist."""
        playlist = self.get_object()
        item = get_object_or_404(PlaylistItem, playlist=playlist, movie_id=movie_id)

        serializer = UpdatePlaylistItemStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item.status = serializer.validated_data["status"]
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

