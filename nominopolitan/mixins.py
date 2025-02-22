"""
This module provides mixins for Django views that enhance CRUD operations with HTMX support,
filtering capabilities, and modal interactions.

Key Components:
- HTMXFilterSetMixin: Adds HTMX attributes to filter forms for dynamic updates
- NominopolitanMixin: Main mixin that provides CRUD view enhancements with HTMX and modal support
"""

from django import forms
from django.db import models

from django.http import Http404
from django.urls import NoReverseMatch, path, reverse
from django.utils.decorators import classonlymethod
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import render
from django.template.response import TemplateResponse

from django.conf import settings
from django.db.models.fields.reverse_related import ManyToOneRel

import json
import logging
log = logging.getLogger("nominopolitan")

from crispy_forms.helper import FormHelper
from django import forms
from django_filters import (
    FilterSet, CharFilter, DateFilter, NumberFilter, 
    BooleanFilter, ModelChoiceFilter, TimeFilter,
    )
from django_filters.filterset import filterset_factory
from neapolitan.views import Role

class HTMXFilterSetMixin:
    """
    Mixin that adds HTMX attributes to filter forms for dynamic updates.
    
    Attributes:
        HTMX_ATTRS (dict): Base HTMX attributes for form fields
        FIELD_TRIGGERS (dict): Mapping of form field types to HTMX trigger events
    """

    HTMX_ATTRS: dict[str, str] = {
        'hx-get': '',
        'hx-include': '[name]',  # Include all named form fields
    }

    FIELD_TRIGGERS: dict[type[forms.Widget] | str, str] = {
        forms.DateInput: 'change',
        forms.TextInput: 'keyup changed delay:300ms',
        forms.NumberInput: 'keyup changed delay:300ms',
        'default': 'change'
    }

    def setup_htmx_attrs(self) -> None:
        """Configure HTMX attributes for form fields and setup crispy form helper."""
        for field in self.form.fields.values():
            widget_class: type[forms.Widget] = type(field.widget)
            trigger: str = self.FIELD_TRIGGERS.get(widget_class, self.FIELD_TRIGGERS['default'])
            attrs: dict[str, str] = {**self.HTMX_ATTRS, 'hx-trigger': trigger}
            field.widget.attrs.update(attrs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.wrapper_class = 'col-auto'
        self.helper.template = 'bootstrap5/layout/inline_field.html'

class NominopolitanMixin:
    """
    Main mixin that enhances Django CRUD views with HTMX support, filtering, and modal functionality.
    
    Attributes:
        namespace (str | None): URL namespace for the view
        templates_path (str): Path to template directory
        base_template_path (str): Path to base template
        use_crispy (bool | None): Enable crispy-forms if installed
        exclude (list[str]): Fields to exclude from list view
        properties (list[str]): Model properties to include in list view
        use_htmx (bool | None): Enable HTMX functionality

        use_modal (bool | None): Enable modal dialogs
        modal_id (str | None): Custom modal element ID
        modal_target (str | None): Allows override of the default modal target
            which is #nominopolitanModalContent. Useful if for example
            the project has a modal with a different id available
            in the base template.

        table_font_size (str | None): Table font size in rem
        table_max_col_width (str | None): Maximum column width in characters
    """

    namespace: str | None = None
    create_form_class: type[forms.ModelForm] | None = None
    templates_path: str = f"nominopolitan/{getattr(settings, 'NOMINOPOLITAN_CSS_FRAMEWORK', 'bootstrap5')}"
    base_template_path: str = f"{templates_path}/base.html"

    use_crispy: bool | None = None

    exclude: list[str] = []
    properties: list[str] = []
    properties_exclude: list[str] = []

    detail_fields: list[str] = []
    detail_exclude: list[str] = []
    detail_properties: list[str] = []
    detail_properties_exclude: list[str] = []

    use_htmx: bool | None = None
    hx_trigger: str | dict[str, str] | None = None

    use_modal: bool | None = None
    modal_id: str | None = None
    modal_target: str | None = None

    table_font_size: str | None = None
    table_max_col_width: str | None = None
    def get_table_font_size(self):
        # The font size for the table (buttons, filters, column headers, rows) in object_list.html
        return self.table_font_size or '0.875' #rem
    
    def get_table_max_col_width(self):
        # The max width for the table columns in object_list.html - in characters
        return self.table_max_col_width or '25' #ch

    def get_framework_styles(self):
        """
        Get framework-specific styles. Override this method and add 
        the new framework name as a key to the returned dictionary.
        
        Returns:
            dict: Framework-specific style configurations
        """
        
        table_font_size = self.get_table_font_size()

        return {
            'bootstrap5': {
                # to make table styling for font size work
                'font-size': f'{table_font_size}rem;',
                # base class for buttons
                'base': 'btn btn-sm py-0',
                # style for buttons
                'button_style': f'font-size: {table_font_size}rem;' ,
                # attributes for filter form fields
                'filter_attrs': {
                    'class': 'form-control-xs small py-1',
                    'style': f'font-size: {table_font_size}rem;'
                },
                # set colours for the action buttons
                'actions': {
                    'View': 'btn-info',
                    'Edit': 'btn-primary',
                    'Delete': 'btn-danger'
                },
                # default colour for extra action buttons
                'extra_default': 'btn-primary',
                # modal class attributes
                'modal_attrs': f'data-bs-toggle="modal" data-bs-target="{self.get_modal_id()}"',
            }
        }


    def list(self, request, *args, **kwargs):
        """
        Handle GET requests for list view, including filtering and pagination.
        
        Returns:
            TemplateResponse: Rendered list view
        """
        queryset = self.get_queryset()
        filterset = self.get_filterset(queryset)
        if filterset is not None:
            queryset = filterset.qs

        if not self.allow_empty and not queryset.exists():
            raise Http404

        paginate_by = self.get_paginate_by()
        if paginate_by is None:
            # Unpaginated response
            self.object_list = queryset
            context = self.get_context_data(
                test_variable="Testing",
                page_obj=None,
                is_paginated=False,
                paginator=None,
                filterset=filterset,
            )
        else:
            # Paginated response
            page = self.paginate_queryset(queryset, paginate_by)
            self.object_list = page.object_list
            context = self.get_context_data(
                test_variable="Testing",
                page_obj=page,
                is_paginated=page.has_other_pages(),
                paginator=page.paginator,
                filterset=filterset,
            )

        return self.render_to_response(context)


    def get_filterset(self, queryset=None):
        """
        Create a dynamic FilterSet class based on provided parameters:
            - filterset_class (in which case the provided class is used); or
            - filterset_fields (in which case a dynamic class is created)
        
        Args:
            queryset: Optional queryset to filter
            
        Returns:
            FilterSet: Configured filter set instance or None
        """
        filterset_class = getattr(self, "filterset_class", None)
        filterset_fields = getattr(self, "filterset_fields", None)

        if filterset_class is None and filterset_fields is not None:
            use_htmx = self.get_use_htmx()
            use_crispy = self.get_use_crispy()

            class DynamicFilterSet(HTMXFilterSetMixin, FilterSet):
                """
                Dynamically create a FilterSet class based on the model fields.

                This class inherits from HTMXFilterSetMixin to add HTMX functionality
                and FilterSet for Django filtering capabilities.
                """
                framework = getattr(settings, 'NOMINOPOLITAN_CSS_FRAMEWORK', 'bootstrap5')
                BASE_ATTRS = self.get_framework_styles()[framework]['filter_attrs']

                # Dynamically create filter fields based on the model's fields
                for field_name in filterset_fields:
                    model_field = self.model._meta.get_field(field_name)
                    field_attrs = BASE_ATTRS.copy()

                    # Handle GeneratedField special case
                    field_to_check = model_field.output_field if isinstance(model_field, models.GeneratedField) else model_field

                    # Create appropriate filter based on field type
                    if isinstance(field_to_check, (models.CharField, models.TextField)):
                        locals()[field_name] = CharFilter(lookup_expr='icontains', widget=forms.TextInput(attrs=field_attrs))
                    elif isinstance(field_to_check, models.DateField):
                        field_attrs['type'] = 'date'
                        locals()[field_name] = DateFilter(widget=forms.DateInput(attrs=field_attrs))
                    elif isinstance(field_to_check, (models.IntegerField, models.DecimalField, models.FloatField)):
                        field_attrs['step'] = 'any'
                        locals()[field_name] = NumberFilter(widget=forms.NumberInput(attrs=field_attrs))
                    elif isinstance(field_to_check, models.BooleanField):
                        locals()[field_name] = BooleanFilter(widget=forms.Select(
                            attrs=field_attrs, choices=((None, '---------'), (True, True), (False, False))))
                    elif isinstance(field_to_check, models.ForeignKey):
                        locals()[field_name] = ModelChoiceFilter(queryset=model_field.related_model.objects.all(), 
                                                                 widget=forms.Select(attrs=field_attrs))
                    elif isinstance(field_to_check, models.TimeField):
                        field_attrs['type'] = 'time'
                        locals()[field_name] = TimeFilter(widget=forms.TimeInput(attrs=field_attrs))
                    else:
                        locals()[field_name] = CharFilter(widget=forms.TextInput(attrs=field_attrs))

                class Meta:
                    model = self.model
                    fields = filterset_fields
               
                def __init__(self, *args, **kwargs):
                    """Initialize the FilterSet and set up HTMX attributes if needed."""
                    super().__init__(*args, **kwargs)
                    if use_htmx:
                        self.setup_htmx_attrs()
                        
            filterset_class = DynamicFilterSet

        if filterset_class is None:
            return None

        return filterset_class(
            self.request.GET,
            queryset=queryset,
            request=self.request,
        )
    
    def _get_all_fields(self):
        fields = [field.name for field in self.model._meta.get_fields()]
            
        # Exclude reverse relations
        fields = [
            field.name for field in self.model._meta.get_fields()
            if not isinstance(field, ManyToOneRel)
        ]
        return fields

    
    def _get_all_properties(self):
        return [name for name in dir(self.model)
                    if isinstance(getattr(self.model, name), property) and name != 'pk'
                ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # determine the starting list of fields (before exclusions)
        if not self.fields or self.fields == '__all__':
            # set to all fields in model
            self.fields = self._get_all_fields()
        elif type(self.fields) == list:
            # check all are valid fields
            all_fields = self._get_all_fields()
            for field in self.fields:
                if field not in all_fields:
                    raise ValueError(f"Field {field} not defined in {self.model.__name__}")
        elif type(self.fields) != list:
            raise TypeError("fields must be a list")        
        else:
            raise ValueError("fields must be '__all__', a list of valid fields or not defined")

        # exclude fields
        if type(self.exclude) == list:
            self.fields = [field for field in self.fields if field not in self.exclude]
        else:
            raise TypeError("exclude must be a list")

        if self.properties:
            if self.properties == '__all__':
                # Set self.properties to a list of every property in self.model
                self.properties = self._get_all_properties()
            elif type(self.properties) == list:
                # check all are valid properties
                all_properties = self._get_all_properties()
                for prop in self.properties:
                    if prop not in all_properties:
                        raise ValueError(f"Property {prop} not defined in {self.model.__name__}")
            elif type(self.properties) != list:
                raise TypeError("properties must be a list or '__all__'")
            
        # exclude properties
        if type(self.properties_exclude) == list:
            self.properties = [prop for prop in self.properties if prop not in self.properties_exclude]
        else:
            raise TypeError("properties_exclude must be a list")

        # determine the starting list of detail_fields (before exclusions)
        if self.detail_fields == '__all__':
            # Set self.detail_fields to a list of every field in self.model
            self.detail_fields = self._get_all_fields()        
        elif not self.detail_fields or self.detail_fields == '__fields__':
            # Set self.detail_fields to self.fields
            self.detail_fields = self.fields
        elif type(self.detail_fields) == list:
            # check all are valid fields
            all_fields = self._get_all_fields()
            for field in self.detail_fields:
                if field not in all_fields:
                    raise ValueError(f"detail_field {field} not defined in {self.model.__name__}")
        elif type(self.detail_fields) != list:
            raise TypeError("detail_fields must be a list or '__all__' or '__fields__' or a list of fields")

        # exclude detail_fields
        if type(self.detail_exclude) == list:
            self.detail_fields = [field for field in self.detail_fields 
                                  if field not in self.detail_exclude]
        else:
            raise TypeError("detail_fields_exclude must be a list")

        # add specified detail_properties            
        if self.detail_properties:
            if self.detail_properties == '__all__':
                # Set self.detail_properties to a list of every property in self.model
                self.detail_properties = self._get_all_properties()
            elif self.detail_properties == '__properties__':
                # Set self.detail_properties to a list of every property in self.model
                self.detail_properties = self.properties
            elif type(self.detail_properties) == list:
                # check all are valid properties
                all_properties = self._get_all_properties()
                for prop in self.detail_properties:
                    if prop not in all_properties:
                        raise ValueError(f"Property {prop} not defined in {self.model.__name__}")
            elif type(self.detail_properties) != list:
                raise TypeError("detail_properties must be a list or '__all__' or '__properties__'")

        # exclude detail_properties
        if type(self.detail_properties_exclude) == list:
            self.detail_properties = [prop for prop in self.detail_properties 
                                  if prop not in self.detail_properties_exclude]
        else:
            raise TypeError("detail_properties_exclude must be a list")
        
    def get_session_key(self):
        """
        Generate a unique session key for storing the original HTMX target.

        This method is called from the render_to_response method when handling HTMX requests
        for the list view. It creates a unique key based on the view's url_base to store
        the original HTMX target in the session.

        Returns:
            str: A unique session key in the format "nominopolitan_list_target_{url_base}"
        """
        return f"nominopolitan_list_target_{self.url_base}"

    def get_original_target(self):
        """
        Retrieve the original HTMX target from the session.

        This method is called in get_context_data() to provide the original target
        in the context for templates.

        Returns:
            str or None: The original HTMX target or None if not set
        """
        return self.request.session.get(self.get_session_key(), None)

    def get_use_htmx(self):
        """
        Determine if HTMX should be used.

        This method is called in multiple places, including get_context_data(),
        get_htmx_target(), and get_use_modal(), to check if HTMX functionality
        should be enabled.

        Returns:
            bool: True if HTMX should be used, False otherwise
        """
        return self.use_htmx is True

    def get_use_modal(self):
        """
        Determine if modal functionality should be used.

        This method is called in get_context_data() to set the 'use_modal' context
        variable for templates. It requires HTMX to be enabled.

        Returns:
            bool: True if modal should be used and HTMX is enabled, False otherwise
        """
        result = self.use_modal is True and self.get_use_htmx()
        return result
    
    def get_modal_id(self):
        """
        Get the ID for the modal element.

        This method is called in get_framework_styles() to set the modal attributes
        for Bootstrap 5.

        Returns:
            str: The modal ID with a '#' prefix
        """
        modal_id = self.modal_id or 'nominopolitanBaseModal'
        return f'#{modal_id}'
    
    def get_modal_target(self):
        """
        Get the target element ID for the modal content.

        This method is called in get_htmx_target() when use_modal is True to
        determine where to render the modal content.

        Returns:
            str: The modal target ID with a '#' prefix
        """
        modal_target = self.modal_target or 'nominopolitanModalContent'
        return f'#{modal_target}'
    
    def get_hx_trigger(self):
        """
        Get the HX-Trigger value for HTMX responses.

        This method is called in render_to_response() to set the HX-Trigger header
        for HTMX responses. It handles string, numeric, and dictionary values for
        the hx_trigger attribute.

        Returns:
            str or None: The HX-Trigger value as a string, or None if not applicable
        """
        if not self.get_use_htmx() or not self.hx_trigger:
            return None
            
        if isinstance(self.hx_trigger, (str, int, float)):
            return str(self.hx_trigger)
        elif isinstance(self.hx_trigger, dict):
            # Validate all keys are strings
            if not all(isinstance(k, str) for k in self.hx_trigger.keys()):
                raise TypeError("HX-Trigger dict keys must be strings")
            return json.dumps(self.hx_trigger)
        else:
            raise TypeError("hx_trigger must be either a string or dict with string keys")

    def get_htmx_target(self):
        """
        Determine the HTMX target for rendering responses.

        This method is called in get_context_data() to set the htmx_target context
        variable for templates. It handles different scenarios based on whether
        HTMX and modal functionality are enabled.

        Returns:
            str or None: The HTMX target as a string with '#' prefix, or None if not applicable
        """
        # only if using htmx
        if not self.get_use_htmx():
            htmx_target = None
        elif self.use_modal:
            htmx_target = self.get_modal_target()
        elif hasattr(self.request, 'htmx') and self.request.htmx.target:
            # return the target of the original list request
            htmx_target = f"#{self.request.htmx.target}"
        else:
            htmx_target = "#content"  # Default target for non-HTMX requests

        return htmx_target

    def get_use_crispy(self):
        """
        Determine if crispy forms should be used.

        This method is called in get_context_data() to set the 'use_crispy' context
        variable for templates. It checks if the crispy_forms app is installed and
        if the use_crispy attribute is explicitly set.

        Returns:
            bool: True if crispy forms should be used, False otherwise

        Note:
            - If use_crispy is explicitly set to True but crispy_forms is not installed,
              it logs a warning and returns False.
            - If use_crispy is not set, it returns True if crispy_forms is installed,
              False otherwise.
        """
        use_crispy_set = self.use_crispy is not None
        crispy_installed = "crispy_forms" in settings.INSTALLED_APPS

        if use_crispy_set:
            if self.use_crispy is True and not crispy_installed:
                log.warning("use_crispy is set to True, but crispy_forms is not installed. Forcing to False.")
                return False
            return self.use_crispy
        return crispy_installed

    @staticmethod
    def get_url(role, view_cls):
        """
        Generate a URL pattern for a specific role and view class.

        This method is used internally by the get_urls method to create individual URL patterns.

        Args:
            role (Role): The role for which to generate the URL.
            view_cls (class): The view class for which to generate the URL.

        Returns:
            path: A Django URL pattern for the specified role and view class.
        """
        return path(
            role.url_pattern(view_cls),
            view_cls.as_view(role=role),
            name=f"{view_cls.url_base}-{role.url_name_component}",
        )

    @classonlymethod
    def get_urls(cls, roles=None):
        """
        Generate a list of URL patterns for all roles or specified roles.

        This method is typically called from the urls.py file of a Django app to generate
        URL patterns for all CRUD views associated with a model.

        Args:
            roles (iterable, optional): An iterable of Role objects. If None, all roles are used.

        Returns:
            list: A list of URL patterns for the specified roles.
        """
        if roles is None:
            roles = iter(Role)
        return [NominopolitanMixin.get_url(role, cls) for role in roles]

    def reverse(self, role, view, object=None):
        """
        Override of neapolitan's reverse method.
        
        Generates a URL for a given role, view, and optional object.
        Handles namespaced and non-namespaced URLs.

        Args:
            role (Role): The role for which to generate the URL.
            view (View): The view class for which to generate the URL.
            object (Model, optional): The model instance for detail, update, and delete URLs.

        Returns:
            str: The generated URL.

        Raises:
            ValueError: If object is None for detail, update, and delete URLs.
        """
        url_name = (
            f"{view.namespace}:{view.url_base}-{role.url_name_component}"
            if view.namespace
            else f"{view.url_base}-{role.url_name_component}"
        )
        url_kwarg = view.lookup_url_kwarg or view.lookup_field

        match role:
            case Role.LIST | Role.CREATE:
                return reverse(url_name)
            case _:
                if object is None:
                    raise ValueError("Object required for detail, update, and delete URLs")
                return reverse(
                    url_name,
                    kwargs={url_kwarg: getattr(object, view.lookup_field)},
                )

    def maybe_reverse(self, view, object=None):
        """
        Override of neapolitan's maybe_reverse method.
        
        Attempts to reverse a URL, returning None if it fails.

        Args:
            view (View): The view class for which to generate the URL.
            object (Model, optional): The model instance for detail, update, and delete URLs.

        Returns:
            str or None: The generated URL if successful, None otherwise.
        """
        try:
            return self.reverse(view, object)
        except NoReverseMatch:
            return None
    
    def get_form_class(self):
        """
        Override get_form_class to remove any non-editable fields where a form_class was not specified.
        
        This method is called by Django's form processing to determine which form class to use.
        It removes non-editable fields from self.fields if a form_class is not explicitly set,
        and uses create_form_class for CREATE operations if specified.

        Returns:
            Form class to be used for the current view.
        """
        if self.fields and not self.form_class:
            non_editable_fields = [
                    field.name for field in self.model._meta.fields 
                    if not field.editable
                ]
            self.fields = [field for field in self.fields if field not in non_editable_fields]

        if self.create_form_class and self.role is Role.CREATE:
            return self.create_form_class

        return super().get_form_class()

    def get_prefix(self):
        """
        Generate a prefix for URL names.

        This method is used in get_context_data to create namespaced URL names.

        Returns:
            str: A prefix string for URL names, including namespace if set.
        """
        return f"{self.namespace}:{self.url_base}" if self.namespace else self.url_base

    def safe_reverse(self, viewname, kwargs=None):
        """
        Safely attempt to reverse a URL, returning None if it fails.

        This method is used in get_context_data to generate URLs for various views.

        Args:
            viewname (str): The name of the view to reverse.
            kwargs (dict, optional): Additional keyword arguments for URL reversing.

        Returns:
            str or None: The reversed URL if successful, None otherwise.
        """
        try:
            return reverse(viewname, kwargs=kwargs)
        except NoReverseMatch:
            return None

    def get_template_names(self):
        """
        Determine the appropriate template names for the current view.

        This method is called by Django's template rendering system to find the correct template.
        It overrides the default behavior to include custom template paths.

        Returns:
            list: A list of template names to be used for rendering.

        Raises:
            ImproperlyConfigured: If neither template_name nor model and template_name_suffix are defined.
        """
        if self.template_name is not None:
            return [self.template_name]

        if self.model is not None and self.template_name_suffix is not None:
            names = [
                f"{self.model._meta.app_label}/"
                f"{self.model._meta.object_name.lower()}"
                f"{self.template_name_suffix}.html",
                f"{self.templates_path}/object{self.template_name_suffix}.html",
            ]
            return names
        msg = (
            "'%s' must either define 'template_name' or 'model' and "
            "'template_name_suffix', or override 'get_template_names()'"
        )
        raise ImproperlyConfigured(msg % self.__class__.__name__)

    def get_context_data(self, **kwargs):
        """
        Prepare and return the context data for template rendering.

        This method extends the base context with additional data specific to the view,
        including URLs for CRUD operations, HTMX-related settings, and related object information.

        Args:
            **kwargs: Additional keyword arguments passed to the method.

        Returns:
            dict: The context dictionary containing all the data for template rendering.
        """
        context = super().get_context_data(**kwargs)

        # Generate and add URLs for create, update, and delete operations
        view_name = f"{self.get_prefix()}-{Role.CREATE.value}"
        context["create_view_url"] = self.safe_reverse(view_name)

        if self.object:
            update_view_name = f"{self.get_prefix()}-{Role.UPDATE.value}"
            context["update_view_url"] = self.safe_reverse(update_view_name, kwargs={"pk": self.object.pk})
            delete_view_name = f"{self.get_prefix()}-{Role.DELETE.value}"
            context["delete_view_url"] = self.safe_reverse(delete_view_name, kwargs={"pk": self.object.pk})

        # Set header title for partial updates
        context["header_title"] = f"{self.url_base.title()}-{self.role.value.title()}"

        # Add template and feature configuration
        context["base_template_path"] = self.base_template_path
        context["use_crispy"] = self.get_use_crispy()
        context["use_htmx"] = self.get_use_htmx()
        context['use_modal'] = self.get_use_modal()
        context["original_target"] = self.get_original_target()

        # Set table styling parameters
        context['table_font_size'] = f"{self.get_table_font_size()}rem"
        context['table_max_col_width'] = f"{self.get_table_max_col_width()}ch"

        # Add HTMX-specific context if enabled
        if self.get_use_htmx():
            context["htmx_target"] = self.get_htmx_target()

        # Add related fields information for list view
        if self.role == Role.LIST and hasattr(self, "object_list"):
            context["related_fields"] = {
                field.name: field.related_model._meta.verbose_name
                for field in self.model._meta.fields
                if field.is_relation
            }

        # Add related objects information for detail view
        if self.role == Role.DETAIL and hasattr(self, "object"):
            context["related_objects"] = {
                field.name: str(getattr(self.object, field.name))
                for field in self.model._meta.fields
                if field.is_relation and getattr(self.object, field.name)
            }

        return context

    def get_success_url(self):
        """
        Determine the URL to redirect to after a successful form submission.

        This method constructs the appropriate success URL based on the current role
        (CREATE, UPDATE, DELETE) and the view's configuration. It uses the namespace
        and url_base attributes to generate the correct URL patterns.

        Returns:
            str: The URL to redirect to after a successful form submission.

        Raises:
            AssertionError: If the model is not defined for this view.
        """
        assert self.model is not None, (
            "'%s' must define 'model' or override 'get_success_url()'"
            % self.__class__.__name__
        )

        url_name = (
            f"{self.namespace}:{self.url_base}-list"
            if self.namespace
            else f"{self.url_base}-list"
        )

        if self.role in (Role.DELETE, Role.UPDATE, Role.CREATE):
            success_url = reverse(url_name)
        else:
            detail_url = (
                f"{self.namespace}:{self.url_base}-detail"
                if self.namespace
                else f"{self.url_base}-detail"
            )
            success_url = reverse(detail_url, kwargs={"pk": self.object.pk})

        return success_url

    def render_to_response(self, context={}):
        """
        Render the response, handling both HTMX and regular requests.

        This method determines the appropriate template and rendering method based on
        whether the request is an HTMX request or a regular request. For HTMX requests,
        it handles partial content updates and sets appropriate HTMX-specific headers.

        Args:
            context (dict): The context dictionary for template rendering.

        Returns:
            HttpResponse: The rendered response, either as a full page or partial content.
        """
        template_names = self.get_template_names()
        template_name = template_names[0] if self.template_name else template_names[1]

        if self.request.htmx:
            if self.role == Role.LIST:
                self.request.session[self.get_session_key()] = f"#{self.request.htmx.target}"
                context["original_target"] = self.get_original_target()
                context['table_font_size'] = f"{self.get_table_font_size()}rem"
                context['table_max_col_width'] = f"{self.get_table_max_col_width()}ch"

            if self.request.headers.get('X-Filter-Request'):
                template_name=f"{template_name}#filtered_results"
            else:
                template_name=f"{template_name}#content"

            response = render(
                request=self.request,
                template_name=f"{template_name}",
                context=context,
            )
            response['HX-Trigger'] = self.get_hx_trigger()
            return response
        else:
            return TemplateResponse(
                request=self.request, template=template_name, context=context
            )
