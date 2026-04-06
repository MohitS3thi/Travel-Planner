from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0005_triproute'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trip',
            name='interests',
            field=models.TextField(blank=True, help_text='Example: food, museums, hiking, nightlife'),
        ),
    ]
