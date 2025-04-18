from django import template

register = template.Library()

@register.filter(name='abs')
def abs_filter(value):
    """Returns the absolute value of a number."""
    try:
        return abs(value)
    except (ValueError, TypeError):
        return value

@register.filter(name='get_item')
def get_item(dictionary, key):
    """Returns the value from a dictionary for the given key."""
    return dictionary.get(key)