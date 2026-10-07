import math
import re

from django import template
from django.utils import timezone
from django.utils.dateformat import format as format_date
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

WORDS_PER_MINUTE = 200
CENSORED_WORD = "****"  # what better_profanity replaces each blocked word with
CENSORED_WORD_HTML = '<span class="censored" title="Filtered word">••••</span>'


@register.filter
def initials(username):
    """'salah.tawafsha' -> 'ST', 'salah' -> 'S'."""
    parts = [part for part in re.split(r"[\W_]+", str(username)) if part]
    return "".join(part[0] for part in parts[:2]).upper() or "?"


@register.filter
def read_time(text):
    """Estimated minutes to read `text`, at least 1."""
    return max(1, math.ceil(len(str(text).split()) / WORDS_PER_MINUTE))


@register.filter
def filtered_count(text):
    """How many words the profanity filter replaced in `text`."""
    return str(text).count(CENSORED_WORD)


@register.filter
def ago(value):
    """'Just now', '5 min ago', '3 h ago', or the date for anything older than a day."""
    seconds = (timezone.now() - value).total_seconds()
    if seconds < 60:
        return "Just now"
    if seconds < 60 * 60:
        return f"{int(seconds // 60)} min ago"
    if seconds < 60 * 60 * 24:
        return f"{int(seconds // 3600)} h ago"
    return format_date(timezone.localtime(value), "M j, Y")


def _inline(text):
    html = escape(text).replace(CENSORED_WORD, CENSORED_WORD_HTML)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
    return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", html)


@register.filter
def censored(text):
    """Plain text with line breaks kept and filtered words shown as dots."""
    return mark_safe("<br>".join(escape(line).replace(CENSORED_WORD, CENSORED_WORD_HTML)
                                 for line in str(text).splitlines()))


@register.filter
def markdown(text):
    """
    Renders the small Markdown subset the editor's Preview tab supports: #/##/### headings,
    "-"/"*" bullet lists, paragraphs, and inline **bold**, *italic* and `code`.
    Text is HTML-escaped before any markup is added, so post bodies can't inject HTML.
    """
    html, paragraph, list_items = [], [], []

    def flush():
        if paragraph:
            html.append("<p>" + "<br>".join(_inline(line) for line in paragraph) + "</p>")
        if list_items:
            html.append("<ul>" + "".join(f"<li>{_inline(item)}</li>" for item in list_items) + "</ul>")
        paragraph.clear()
        list_items.clear()

    for line in str(text).splitlines():
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        list_item = re.match(r"^\s*[-*]\s+(.*)$", line)
        if heading:
            flush()
            level = len(heading.group(1)) + 1
            html.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif list_item:
            if paragraph:
                flush()
            list_items.append(list_item.group(1))
        elif not line.strip():
            flush()
        else:
            if list_items:
                flush()
            paragraph.append(line)
    flush()

    return mark_safe("".join(html))
