from django import template

register = template.Library()

@register.filter
def charttypes(value):
    print(value)
    ret = []
    for item in value:
        ret.append(item.charttype)
    return list(set(ret))

