from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Permet d'accéder à dictionnaire[cle_variable] depuis un template"""
    if dictionary is None:
        return None
    return dictionary.get(key)