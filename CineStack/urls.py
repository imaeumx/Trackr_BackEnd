"""
CineStack URL Configuration
"""
from django.urls import path, include
from django.http import JsonResponse

def home(request):
    return JsonResponse({
        'status': 'online',
        'service': 'TrackR Backend API',
        'endpoints': {
            'login': '/api/auth/login/',
            'register': '/api/auth/register/',
            'movies': '/api/movies/',
            'playlists': '/api/playlists/',
            'tmdb_search': '/api/tmdb/search/',
        }
    })

urlpatterns = [
    path('', home, name='home'),
    path('api/', include('playlist.urls')),
]