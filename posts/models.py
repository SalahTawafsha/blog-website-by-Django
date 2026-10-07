import datetime
import random

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from better_profanity import profanity

ALLOWED_NUM_OF_CENSORED_WORDS = 3


# Create your models here.
class PublishedPostManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status="P").order_by("-publish")


class DraftManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status="D").order_by("-publish")


class Post(models.Model):
    STATUS_CHOICES = (
        ("D", "Draft"),
        ("P", "Published"),
    )
    objects = models.Manager()
    published_objects = PublishedPostManager()
    all_objects = DraftManager()
    title = models.CharField("Post Title", max_length=100)
    slug = models.SlugField(unique=True, blank=False, null=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField("Post body", max_length=5000)
    publish = models.DateTimeField("Data of publish", default=timezone.now)
    created = models.DateTimeField("Data of create", auto_now_add=True)
    updated = models.DateTimeField("Data of last update", auto_now=True)
    status = models.CharField(default="P",
                              max_length=10,
                              choices=STATUS_CHOICES)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            self.uniquify()

        self.body = profanity.censor(self.body)

        censored_words_count = self.body.count('****')

        if censored_words_count > ALLOWED_NUM_OF_CENSORED_WORDS:
            self.author.usertracking.increment_warnings()
            self.author.usertracking.save()
            super().save(*args, **kwargs)
            return True

        super().save(*args, **kwargs)
        return False

    def uniquify(self):
        slug = self.slug
        self.slug = slug + "-" + str(random.randint(0, 1000000000))


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    user_name = models.CharField("Author Name", max_length=50)
    email = models.EmailField("Author Email", max_length=256)
    body = models.TextField("Comment Body", max_length=500)
    created = models.DateTimeField("Data of create", auto_now_add=True)
    updated = models.DateTimeField("Data of last update", auto_now=True)
    isActive = models.BooleanField("is active", default=True)

    def is_there_comment_in_recent_30_sec(self):
        try:
            Comment.objects.get(email=self.email, created__gte=timezone.now() - datetime.timedelta(seconds=30))
            return True
        except Comment.DoesNotExist:
            return False

    def save(self, *args, **kwargs):
        if self.is_there_comment_in_recent_30_sec():
            raise Exception("You can't comment twice in 30 seconds.")

        self.body = profanity.censor(self.body)

        censored_words_count = self.body.count('****')

        if censored_words_count > ALLOWED_NUM_OF_CENSORED_WORDS:
            try:
                user = User.objects.get(username=self.user_name)
                user.usertracking.increment_warnings()
                user.usertracking.save()
            except User.DoesNotExist:
                pass
            super().save(*args, **kwargs)
            return True

        super().save(*args, **kwargs)
        return False

    def __str__(self):
        return self.body
