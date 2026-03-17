from django import template
from django.contrib.admin.views.main import PAGE_VAR
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def admin_page_url(cl, page_num):
    """Return URL for the given 0-based page number, preserving query params."""
    return cl.get_query_string({PAGE_VAR: page_num})
