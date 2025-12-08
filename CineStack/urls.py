"""
CineStack URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def home(request):
    return HttpResponse("""
        <h1>Trackr Backend API</h1>
        <p>Status: Online</p>
        <ul>
            <li><a href="/admin/">Admin Panel</a></li>
            <li><a href="/api/auth/login/">API Login</a></li>
            <li><a href="/api/">API Endpoints</a></li>
        </ul>
    """)

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('rest_framework.urls')),  # DRF auth endpoints
    path('api/', include('playlist.urls')),  # Expose all playlist endpoints
]