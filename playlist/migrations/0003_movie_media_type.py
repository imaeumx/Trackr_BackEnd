from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("playlist", "0002_movie_tmdb_id_movie_youtube_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="movie",
            name="media_type",
            field=models.CharField(choices=[("movie", "Movie"), ("tv", "TV Show")], default="movie", max_length=16),
        ),
        migrations.AlterField(
            model_name="movie",
            name="tmdb_id",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="movie",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tmdb_id__isnull", False)),
                fields=("tmdb_id", "media_type"),
                name="playlist_movie_unique_tmdb_media_type",
            ),
        ),
    ]
