"""web filters template tags"""
from django import template

register = template.Library()

@register.filter
def charttypes(value):
    """get unique chart types"""
    ret = []
    for item in value:
        ret.append(item.charttype)
    return list(set(ret))
