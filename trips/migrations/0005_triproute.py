from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0004_place_is_one_day_visit_place_return_date_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TripRoute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=180)),
                ('start_key', models.CharField(max_length=80)),
                ('start_name', models.CharField(max_length=160)),
                ('start_lat', models.DecimalField(decimal_places=6, max_digits=9)),
                ('start_lng', models.DecimalField(decimal_places=6, max_digits=9)),
                ('end_key', models.CharField(max_length=80)),
                ('end_name', models.CharField(max_length=160)),
                ('end_lat', models.DecimalField(decimal_places=6, max_digits=9)),
                ('end_lng', models.DecimalField(decimal_places=6, max_digits=9)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('trip', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='routes', to='trips.trip')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
