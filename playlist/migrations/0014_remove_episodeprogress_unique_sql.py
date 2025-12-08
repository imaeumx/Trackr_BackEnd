from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("playlist", "0013_merge_20251207_2345"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS playlist_episodeprogress_user_id_series_id_season_episode_uniq;",
            reverse_sql="",
        ),
    ]
