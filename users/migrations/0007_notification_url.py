# Generated by Django 4.2.5 on 2023-09-14 08:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='url',
            field=models.URLField(default='null', max_length=100),
            preserve_default=False,
        ),
    ]