from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("playlist", "0010_add_did_not_finish_status"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="episodeprogress",
            options={
                "ordering": ["series", "season", "episode"],
            },
        ),
    ]
