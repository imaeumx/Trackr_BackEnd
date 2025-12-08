from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("playlist", "0009_review"),
    ]

    operations = [
        migrations.AlterField(
            model_name="playlistitem",
            name="status",
            field=models.CharField(
                choices=[
                    ("to_watch", "To Watch"),
                    ("watching", "Watching"),
                    ("watched", "Watched"),
                    ("did_not_finish", "Did Not Finish"),
                ],
                default="to_watch",
                max_length=32,
            ),
        ),
    ]
