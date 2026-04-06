from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0007_trip_end_date_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='itineraryitem',
            name='end_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itineraryitem',
            name='start_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
