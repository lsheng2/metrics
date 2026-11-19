from django import template

from ui_web.utils.color_utils import ColorUtils

register = template.Library()


@register.filter
def initials(display_name: str) -> str:
    if not display_name:
        return "?"

    words = display_name.strip().split()

    if not words:
        return "?"

    if len(words) == 1:
        word = words[0]
        if len(word) >= 2:
            return (word[0] + word[1]).upper()
        elif len(word) == 1:
            return word[0].upper()
        else:
            return "?"

    first_letter = words[0][0] if words[0] else ""
    last_letter = words[-1][0] if words[-1] else ""

    return (first_letter + last_letter).upper()


@register.filter
def avatar_slot(display_name: str) -> int:
    return ColorUtils.palette_slot(display_name)
