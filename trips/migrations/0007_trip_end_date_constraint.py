from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0006_alter_trip_interests'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='trip',
            constraint=models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='trip_end_date_on_or_after_start_date',
            ),
        ),
    ]
