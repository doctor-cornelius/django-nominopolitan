"""
This module contains custom template tags for the Nominopolitan package.

It includes functions for generating action links, displaying object details,
and rendering object lists with customized formatting.

Key components:
- action_links: Generates HTML for action buttons (View, Edit, Delete, etc.)
- object_detail: Renders details of an object, including fields and properties
- object_list: Creates a list view of objects with customized field display
- get_proper_elided_page_range: Generates a properly elided page range for pagination

The module adapts to different CSS frameworks and supports HTMX and modal functionality.
"""

from typing import Any, Dict, List, Optional, Tuple

from django import template
from django.utils.safestring import mark_safe
from django.core.exceptions import FieldDoesNotExist
from django.conf import settings


import logging
log = logging.getLogger("nominopolitan")

register = template.Library()

def action_links(view: Any, object: Any) -> str:
    """
    Generate HTML for action links (buttons) for a given object.

    Args:
        view: The view instance
        object: The object for which actions are being generated

    Returns:
        str: HTML string of action buttons
    """
    framework: str = getattr(settings, 'NOMINOPOLITAN_CSS_FRAMEWORK', 'bootstrap5')
    styles: Dict[str, Any] = view.get_framework_styles()[framework]

    prefix: str = view.get_prefix()
    use_htmx: bool = view.get_use_htmx()
    use_modal: bool = view.get_use_modal()

    default_target: str = view.get_htmx_target() # this will be prepended with a #

    # Standard actions with framework-specific button classes
    actions: List[Tuple[str, str, str, str, bool, str]] = [
        (url, name, styles['actions'][name], default_target, False, styles["modal_attrs"])
        for url, name in [
            (view.safe_reverse(f"{prefix}-detail", kwargs={"pk": object.pk}), "View"),
            (view.safe_reverse(f"{prefix}-update", kwargs={"pk": object.pk}), "Edit"),
            (view.safe_reverse(f"{prefix}-delete", kwargs={"pk": object.pk}), "Delete"),
        ]
        if url is not None
    ]

    # Add extra actions if defined
    extra_actions: List[Dict[str, Any]] = getattr(view, "extra_actions", [])
    for action in extra_actions:
        url: Optional[str] = view.safe_reverse(
            action["url_name"],
            kwargs={"pk": object.pk} if action.get("needs_pk", True) else None,
        )
        if url is not None:
            htmx_target: str = action.get("htmx_target", default_target)
            if htmx_target and not htmx_target.startswith("#"):
                htmx_target = f"#{htmx_target}"
            button_class: str = action.get("button_class", styles['extra_default'])
            
            show_modal: bool = action.get("display_modal", view.get_use_modal())
            modal_attrs: str = styles["modal_attrs"] if show_modal else " "
            
            actions.append((
                url, 
                action["text"], 
                button_class, 
                htmx_target, 
                action.get("hx_post", False),
                modal_attrs
            ))

    # set up links for all actions (regular and extra)
    # note for future - could simplify by just conditionally adding hx-disable if not use_htmx
    links: List[str] = [
        f"<div class='btn-group btn-group-sm'>" +
        " ".join([
            f"<a href='{url}' class='{styles['base']} {button_class}' style='{styles['button_style']}' "
            + (f"hx-{'post' if hx_post else 'get'}='{url}' " if use_htmx else "")
            + (f"hx-target='{target}' " if use_htmx else "")
            + (f"hx-replace-url='true' hx-push-url='true' " if use_htmx and not view.get_use_modal() else "")
            + (f"{modal_attrs} " if use_modal else "")
            + f">{anchor_text}</a>"
            for url, anchor_text, button_class, target, hx_post, modal_attrs in actions
        ]) +
        "</div>"
    ]

    return mark_safe(" ".join(links))


@register.inclusion_tag(f"nominopolitan/{getattr(settings, 'NOMINOPOLITAN_CSS_FRAMEWORK', 'bootstrap')}/partial/detail.html")
def object_detail(object, view):
    """
    Display both fields and properties for an object detail view.

    Args:
        object: The object to display
        view: The view instance

    Returns:
        dict: Context for rendering the detail template
    """
    def iter():
        # Handle regular fields
        for f in view.detail_fields:
            field = object._meta.get_field(f)
            if field.is_relation:
                value = str(getattr(object, f))
            else:
                value = field.value_to_string(object)
            yield (field.verbose_name, value)

        # Handle properties
        for prop in view.detail_properties:
            value = str(getattr(object, prop))
            name = prop.replace('_', ' ').title()
            yield (name, value)

    return {
        "object": iter(),
    }


@register.inclusion_tag(
        f"nominopolitan/{getattr(settings, 'NOMINOPOLITAN_CSS_FRAMEWORK', 'bootstrap')}/partial/list.html", 
        takes_context=True
        )
def object_list(context, objects, view):
    """
    Override default to set value = str()
    instead of value_to_string(). This allows related fields
    to be displayed correctly (not just the id)
    """
    fields = view.fields
    properties = getattr(view, "properties", []) or []

    # Headers for fields - get the related model's verbose_name for relation fields
    field_headers = []
    for f in fields:
        field_headers.append(f.replace('_', ' ').title())

    # Headers for properties with proper capitalization
    property_headers = [prop.replace("_", " ").title() for prop in properties]
    headers = field_headers + property_headers

    import locale

    object_list = [
        {
            "object": object,
            "fields": [
                (
                    str(getattr(object, f).strftime('%d/%m/%Y'))
                    if object._meta.get_field(f).get_internal_type() == 'DateField' and getattr(object, f) is not None
                    else str(getattr(object, f))
                    if object._meta.get_field(f).is_relation
                    else object._meta.get_field(f).value_to_string(object)
                )
                for f in fields
            ]
            + [str(getattr(object, prop)) for prop in properties],
            "actions": action_links(view, object),
        }
        for object in objects
    ]

    return {
        "headers": headers,
        "object_list": object_list,
    }

@register.simple_tag
def get_proper_elided_page_range(paginator, number, on_each_side=1, on_ends=1):
    """
    Return a list of page numbers with proper elision for pagination.

    Args:
        paginator: The Django Paginator instance
        number: The current page number
        on_each_side: Number of pages to show on each side of the current page
        on_ends: Number of pages to show at the beginning and end of the range

    Returns:
        list: A list of page numbers and ellipsis characters
    """
    page_range = paginator.get_elided_page_range(
        number=number,
        on_each_side=1,
        on_ends=1
    )
    return page_range



