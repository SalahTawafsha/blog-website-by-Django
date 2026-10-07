import datetime
import math

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django import forms
from django.db import OperationalError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from ChatGPT.GPT import GPT
from users.models import MAX_ALLOWED_POST_POSTS_IN_DAY, MAX_ALLOWED_READ_POSTS_IN_DAY, CreatePostNotification
from .models import Post, Comment, ALLOWED_NUM_OF_CENSORED_WORDS

PAGE_SIZE = 4
COMMENT_COOLDOWN_SECONDS = 30


class PostForm(forms.Form):
    title = forms.CharField(label="Title", max_length=100)
    body = forms.CharField(label="Body", max_length=5000,
                           widget=forms.Textarea(attrs={'cols': 80, 'rows': 20}))


class AddCommentForm(forms.Form):
    # the author's name and email come from request.user, so only the text is submitted
    body = forms.CharField(label="Comment", max_length=2000,
                           widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Share your thoughts…"}))


def censored_words_warning(kind):
    return (f"Your last {kind} used more than {ALLOWED_NUM_OF_CENSORED_WORDS} blocked words, "
            f"so they were hidden. Repeated warnings may limit your account.")


# Create your views here.
def index(request):
    if not request.user.is_authenticated:
        return redirect("index")

    try:
        # use my manager to get published posts
        published_posts = (Post.published_objects.all()
                           .select_related("author")
                           .annotate(likes_count=Count("users_liked", distinct=True),
                                     comments_count=Count("comment", distinct=True))
                           .order_by("-updated"))
        paginator = Paginator(published_posts, PAGE_SIZE)

        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            "page_obj": page_obj,
        }

        if request.user.is_authenticated:
            if not request.user.usertracking.is_can_read_post():
                messages.error(request, f"You can't read posts since you reach max allowed"
                                        f" posts in day that is {MAX_ALLOWED_READ_POSTS_IN_DAY}")

            notifications = (CreatePostNotification.objects.filter(user=request.user)
                             .select_related("post", "post__author"))

            context["notifications"] = notifications

            tracking = request.user.usertracking
            tracking.is_can_post_post()  # resets yesterday's counter if it was maxed out
            context["posts_today"] = tracking.day_create_posts_num
            context["max_posts_per_day"] = MAX_ALLOWED_POST_POSTS_IN_DAY
            context["reads_left"] = max(0, MAX_ALLOWED_READ_POSTS_IN_DAY - tracking.day_read_posts_num)

        return render(request, "posts/index.html", context)
    except OperationalError:
        return render(request, "database_error.html")


def comment_wait_seconds(user):
    """Seconds until `user` may comment again (comments are limited to one per COMMENT_COOLDOWN_SECONDS)."""
    since = timezone.now() - datetime.timedelta(seconds=COMMENT_COOLDOWN_SECONDS)
    last_comment = Comment.objects.filter(email=user.email, created__gte=since).order_by("-created").first()
    if not last_comment:
        return 0
    return max(0, math.ceil((last_comment.created - since).total_seconds()))


def post_detail_context(request, post, form, **extra):
    user = request.user
    tracking = user.usertracking
    is_author = post.author == user

    context = {
        "post": post,
        "form": form,
        "is_author": is_author,
        "comments": post.comment_set.all(),
        "likes_count": post.users_liked.count(),
        "dislikes_count": post.users_disliked.count(),
        "user_liked": tracking.posts_likes.filter(id=post.id).exists(),
        "user_disliked": tracking.posts_dislikes.filter(id=post.id).exists(),
        "subscribers_count": post.author.subscribed_users.count(),
        "is_subscribed": tracking.subscriptions.filter(id=post.author_id).exists(),
        "comment_cooldown": COMMENT_COOLDOWN_SECONDS,
        "comment_wait_seconds": comment_wait_seconds(user),
        "blocked_until": tracking.date_of_end_block if tracking.is_blocked() else None,
    }

    if not is_author:
        reads_used = min(tracking.day_read_posts_num, MAX_ALLOWED_READ_POSTS_IN_DAY)
        context.update({
            "reads_used": reads_used,
            "max_reads": MAX_ALLOWED_READ_POSTS_IN_DAY,
            "reads_left": MAX_ALLOWED_READ_POSTS_IN_DAY - reads_used,
            "read_dots": [i < reads_used for i in range(MAX_ALLOWED_READ_POSTS_IN_DAY)],
        })

    context.update(extra)
    return context


def post_details(request, slug):
    if not request.user.is_authenticated:
        return redirect("index")

    try:
        post = get_object_or_404(Post, slug=slug)
        user = request.user
        is_author = post.author == user

        CreatePostNotification.objects.filter(post=post, user=user).delete()

        already_read = user.usertracking.read_posts.filter(id=post.id).exists()
        if not is_author and not already_read and not user.usertracking.is_can_read_post():
            return redirect("index")

        if request.GET.get("edit") or request.method == "POST":
            grammar_fixed = request.method == "GET" and bool(request.GET.get("grammar"))
            if not is_author or user.usertracking.is_blocked():
                return redirect("post_details", slug=post.slug)

            if request.method == "POST":
                form = PostForm(request.POST)
                if form.is_valid():
                    post.title = form.cleaned_data["title"]
                    post.body = form.cleaned_data["body"]
                    if post.save():
                        messages.warning(request, censored_words_warning("post"))
                    # saving gives the post a new slug, so send the author to its new URL
                    return redirect("post_details", slug=post.slug)
            else:
                body = GPT.fix_grammar(post.body) if grammar_fixed else post.body
                form = PostForm(initial={"title": post.title, "body": body})

            return render(request, "posts/postDetail.html", {
                "post": post,
                "form": form,
                "edit": True,
                "grammar_fixed": grammar_fixed,
            })

        if not is_author:
            user.usertracking.increment_read_posts(post)

        form = AddCommentForm()
        return render(request, "posts/postDetail.html", post_detail_context(request, post, form))
    except OperationalError:
        return render(request, "database_error.html")


def add_comment(request):
    if not request.user.is_authenticated:
        return redirect("index")
    if request.method != "POST":
        return redirect("posts")

    try:
        user = request.user
        post = get_object_or_404(Post.published_objects, id=request.POST.get("post_id"))
        form = AddCommentForm(request.POST)

        # the page itself explains a block or the 30-second wait, and keeps the typed comment
        if form.is_valid() and not user.usertracking.is_blocked() and not comment_wait_seconds(user):
            comment = Comment(post=post, user_name=user.username, email=user.email,
                              body=form.cleaned_data["body"])
            if comment.save():
                messages.warning(request, censored_words_warning("comment"))
            form = AddCommentForm()

        return render(request, "posts/postDetail.html", post_detail_context(request, post, form))
    except OperationalError:
        return render(request, "database_error.html")


def create_post_context(user, form):
    tracking = user.usertracking
    is_blocked = tracking.is_blocked()
    limit_reached = not tracking.is_can_post_post()  # also resets yesterday's maxed-out counter
    posts_today = tracking.day_create_posts_num

    return {
        "form": form,
        "posts_today": posts_today,
        "max_posts_per_day": MAX_ALLOWED_POST_POSTS_IN_DAY,
        "posts_left": max(0, MAX_ALLOWED_POST_POSTS_IN_DAY - posts_today),
        "quota_segments": [i < posts_today for i in range(MAX_ALLOWED_POST_POSTS_IN_DAY)],
        "limit_reached": limit_reached,
        "blocked_until": tracking.date_of_end_block if is_blocked else None,
        "publishing_paused": is_blocked or limit_reached,
    }


def add_post(request):
    if not request.user.is_authenticated:
        return redirect("index")

    try:
        if request.method == "POST":
            form = PostForm(request.POST)
            context = create_post_context(request.user, form)

            # the page explains why publishing is paused, so just keep the draft on screen
            if context["publishing_paused"] or not form.is_valid():
                return render(request, "posts/create_post.html", context)

            title = form.cleaned_data["title"]
            author = request.user
            body = form.cleaned_data["body"]

            post = Post(title=title, author=author, body=body)
            if post.save():
                messages.warning(request, censored_words_warning("post"))

            request.user.usertracking.increment_num_of_created_posts()
            for user_tracking in request.user.subscribed_users.all():
                (CreatePostNotification.objects.
                 create(user=user_tracking.user,
                        post=post,
                        message=f"{request.user.username} create new post '{post.title}'", ))
            return HttpResponseRedirect(reverse("post_details", args=(post.slug,)))

        return render(request, "posts/create_post.html", create_post_context(request.user, PostForm()))
    except OperationalError:
        return render(request, "database_error.html")
