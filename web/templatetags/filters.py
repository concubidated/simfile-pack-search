"""web filters template tags"""
from django import template
from datetime import timedelta
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
def is_new(date_scanned, days=30):
    return date_scanned > timezone.now() - timedelta(days=days)