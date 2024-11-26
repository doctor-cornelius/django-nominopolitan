from django.shortcuts import render

from neapolitan.views import CRUDView
from nominopolitan.mixins import NominopolitanMixin

from django import forms
from . import models
from . import forms

class BookCRUDView(NominopolitanMixin, CRUDView):
    model = models.Book
    fields = [
        "title",
        "author",
        "published_date",
        "isbn",
        "pages",
    ]
    namespace = "sample"
    base_template_path = "django_nominopolitan/base.html"
    form_class = forms.BookForm
    use_htmx = True
    htmx_crud_target = "crud_target"


class AuthorCRUDView(NominopolitanMixin, CRUDView):
    model = models.Author
    fields = [
        "name",
        "bio",
        "birth_date",
    ]
    namespace = "sample"
    use_htmx = True
    base_template_path = "django_nominopolitan/base.html"
    extra_actions = [
        {
            "url_name": "home",  # namespace:url_pattern
            "text": "Home",
            "needs_pk": False,  # if the URL needs the object's primary key
        },
        {
            "url_name": "sample:author-detail",
            "text": "View Again",
            "needs_pk": True,  # if the URL doesn't need the object's primary key
        },
    ]
