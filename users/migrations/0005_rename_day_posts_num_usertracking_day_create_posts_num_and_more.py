# Generated by Django 4.2.5 on 2023-09-14 05:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_usertracking_allowed_read_post_date'),
    ]

    operations = [
        migrations.RenameField(
            model_name='usertracking',
            old_name='day_posts_num',
            new_name='day_create_posts_num',
        ),
        migrations.RenameField(
            model_name='usertracking',
            old_name='read_posts_num',
            new_name='day_read_posts_num',
        ),
    ]
