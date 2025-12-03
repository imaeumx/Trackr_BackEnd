from django.contrib import admin
from django.contrib import messages
from .models import Movie, Playlist, PlaylistItem


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "release_year", "created_at")
    search_fields = ("title",)
    list_filter = ("release_year",)
    ordering = ("-created_at",)


class PlaylistItemInline(admin.TabularInline):
    model = PlaylistItem
    extra = 1
    autocomplete_fields = ("movie",)
    can_delete = True  # Allow deleting items in inline
    show_change_link = True  # Show link to edit item


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "movie_count", "watched_count", "created_at")
    search_fields = ("title",)
    inlines = [PlaylistItemInline]
    ordering = ("-updated_at",)
    
    # Override delete_queryset for bulk delete
    def delete_queryset(self, request, queryset):
        """Custom delete to handle cascading properly."""
        count = queryset.count()
        for obj in queryset:
            obj.delete()
        self.message_user(
            request,
            f"Successfully deleted {count} playlist(s).",
            messages.SUCCESS
        )
    
    # Override delete_model for single delete
    def delete_model(self, request, obj):
        """Custom delete to handle cascading properly."""
        title = obj.title
        obj.delete()
        self.message_user(
            request,
            f"Successfully deleted playlist '{title}'.",
            messages.SUCCESS
        )
    
    # Explicitly allow deletion
    def has_delete_permission(self, request, obj=None):
        return True
    
    class Media:
        js = ()
        css = {}


@admin.register(PlaylistItem)
class PlaylistItemAdmin(admin.ModelAdmin):
    list_display = ("id", "playlist", "movie", "status", "added_at")
    list_filter = ("status", "playlist")
    autocomplete_fields = ("movie", "playlist")
