from django.shortcuts import render

from neapolitan.views import CRUDView
from nominopolitan.mixins import NominopolitanMixin

from django import forms
from . import models


class BookForm(forms.ModelForm):
    class Meta:
        model = models.Book
        fields = [
            "author",
            "published_date",
            "isbn",
            "pages",
            "description",
        ]
        widgets = {
            "submission_date": forms.DateInput(attrs={"type": "date"}),
        }


class BookCRUDView(NominopolitanMixin, CRUDView):
    model = models.Book
    namespace = "sample"
    base_template_path = "django_nominopolitan/base.html"
    form_class = BookForm
    # use_crispy = True
    fields = [
        "author", "published_date", "isbn", "pages",
    ]


class AuthorCRUDView(NominopolitanMixin, CRUDView):
    model = models.Author
    namespace = "sample"
    base_template_path = "django_nominopolitan/base.html"
    fields = [
        "name",
        "bio",
        "birth_date",
    ]
