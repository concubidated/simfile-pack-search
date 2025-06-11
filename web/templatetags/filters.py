"""web filters template tags"""
from datetime import timedelta
from django import template
from django.utils import timezone

register = template.Library()

@register.filter
def charttypes(value):
    """get unique chart types"""
    ret = []
    for item in value:
        ret.append(item.charttype)
    return list(set(ret))

@register.filter
def is_new(date_scanned, days=14):
    """is this pack new?"""
    return date_scanned > timezone.now() - timedelta(days=days)
