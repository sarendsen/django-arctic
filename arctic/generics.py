from __future__ import (division, unicode_literals)
from collections import OrderedDict

import extra_views
from django.conf import settings
from django.contrib.auth import (authenticate, login, logout)
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import (FieldDoesNotExist, ImproperlyConfigured,
                                    ValidationError)
from django.core.paginator import InvalidPage
from django.core.urlresolvers import (NoReverseMatch, reverse)
from django.db.models.deletion import (Collector, ProtectedError)
from django.forms.widgets import Media
from django.http import Http404
from django.shortcuts import (redirect, render, resolve_url)
from django.utils.formats import get_format
from django.utils.http import (is_safe_url, quote)
from django.utils.text import capfirst
from django.utils.translation import ugettext as _
from django.utils.translation import get_language
from django.views import generic as base

from .mixins import (FormMediaMixin, FormMixin, ListMixin, RoleAuthentication,
                     SuccessMessageMixin)
from .paginator import IndefinitePaginator
from .utils import (arctic_setting, find_attribute, get_field_class,
                    find_field_meta, menu, reverse_url, view_from_url)


class View(RoleAuthentication, base.View):
    """
    This view needs to be used for all Arctic views, except the LoginView.

    It includes integration with the Arctic user interface elements, such as
    the menu, site logo, site title, page title and breadcrumbs.
    """

    page_title = ''
    page_description = ''
    breadcrumbs = None
    tabs = None
    requires_login = True
    urls = {}
    form_display = None

    def dispatch(self, request, *args, **kwargs):
        """
        Most views in a CMS require a login, so this is the default setup.

        If a login is not required then the requires_login property
        can be set to False to disable this.
        """
        if self.requires_login:
            if settings.LOGIN_URL is None or settings.LOGOUT_URL is None:
                raise ImproperlyConfigured(
                    'LOGIN_URL and LOGOUT_URL '
                    'has to be defined if requires_login is True'
                )

            if not request.user.is_authenticated():
                return redirect('%s?next=%s' % (
                    resolve_url(settings.LOGIN_URL),
                    quote(request.get_full_path())))

        return super(View, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(View, self).get_context_data(**kwargs)
        context['page_title'] = self.get_page_title()
        context['page_description'] = self.get_page_description()
        context['menu'] = menu(user=self.request.user, request=self.request)
        context['urls'] = self.get_urls()
        context['breadcrumbs'] = self.get_breadcrumbs()
        context['tabs'] = self.get_tabs()
        context['index_url'] = self.get_index_url()
        context['SITE_NAME'] = self.get_site_name()
        context['SITE_TITLE'] = self.get_site_title()
        context['SITE_LOGO'] = self.get_site_logo()
        context['SIDEBAR_BACKGROUND'] = self.get_sidebar_background()
        context['SIDEBAR_COLOR'] = self.get_sidebar_color()
        context['SIDEBAR_ALT_COLOR'] = self.get_sidebar_alt_color()
        context['HIGHLIGHT_BACKGROUND'] = self.get_highlight_background()
        context['HIGHLIGHT_COLOR'] = self.get_highlight_color()
        context['DATETIME_FORMATS'] = self.get_datetime_formats()
        context['LOGIN_URL'] = self.get_login_url()
        context['LOGOUT_URL'] = self.get_logout_url()
        context['media'] = self.media
        context['form_display'] = self.get_form_display()
        return context

    def get_urls(self):
        """
        Used for resolving urls when displaying nested objects, see arctic_url.

        For example, generally you just have /foo/create as
        a url, but with nested, you may have: /foo/<id>/bar/create/ and <id>
        would be a parent id. These are then required to resolve urls.

        @returns
        {named_url, (url_param, url_param),}
        || {named_url, [url_param, url_param],}

        if you provide a list and in this list there are strings, it will try
        to get field of that item. This is especially useful for listviews with
        action_links and field_links.
        """
        return self.urls

    def get_breadcrumbs(self):
        """
        Breadcrumb format: (('name', 'url'), ...) or None if not used.
        """
        if not self.breadcrumbs:
            return None
        else:
            allowed_breadcrumbs = []
            for breadcrumb in self.breadcrumbs:

                # check permission based on named_url
                if breadcrumb[1] is not None \
                        and not view_from_url(
                            breadcrumb[1]).has_permission(self.request.user):
                    continue

                allowed_breadcrumbs.append(breadcrumb)
            return allowed_breadcrumbs

    def get_tabs(self):
        """
        Tabs format: (('name', 'url'), ...) or None if tabs are not used.
        """
        if not self.tabs:
            return None
        else:
            allowed_tabs = []
            for tab in self.tabs:

                # check permission based on named_url
                if not view_from_url(tab[1]).has_permission(self.request.user):
                    continue

                allowed_tabs.append(tab)
            return allowed_tabs

    def get_page_title(self):
        return self.page_title

    def get_page_description(self):
        return self.page_description

    def get_site_logo(self):
        return arctic_setting('ARCTIC_SITE_LOGO')

    def get_site_name(self):
        return arctic_setting('ARCTIC_SITE_NAME')

    def get_site_title(self):
        return getattr(settings, 'ARCTIC_SITE_TITLE',
                       self.get_site_name())

    def get_sidebar_color(self):
        return getattr(settings, 'ARCTIC_SIDEBAR_COLOR', None)

    def get_sidebar_alt_color(self):
        return getattr(settings, 'ARCTIC_SIDEBAR_ALT_COLOR', None)

    def get_sidebar_background(self):
        return getattr(settings, 'ARCTIC_SIDEBAR_BACKGROUND', None)

    def get_highlight_color(self):
        return getattr(settings, 'ARCTIC_HIGHLIGHT_COLOR', None)

    def get_highlight_background(self):
        return getattr(settings, 'ARCTIC_HIGHLIGHT_BACKGROUND', None)

    def get_index_url(self):
        try:
            return reverse(getattr(settings, 'ARCTIC_INDEX_URL', 'index'))
        except NoReverseMatch:
            return '/'

    def get_datetime_formats(self):
        dtformats = {}

        dtformats['SHORT_DATE'] = get_format('DATE_INPUT_FORMATS',
                                             get_language())[0]
        dtformats['TIME'] = get_format('TIME_INPUT_FORMATS',
                                       get_language())[0]
        dtformats['SHORT_DATETIME'] = get_format('DATETIME_INPUT_FORMATS',
                                                 get_language())[0]

        return dtformats

    def get_login_url(self):
        login_url = getattr(settings, 'LOGIN_URL', 'login')
        return reverse(login_url) if login_url else None

    def get_logout_url(self):
        logout_url = getattr(settings, 'LOGOUT_URL', 'logout')
        return reverse(logout_url) if logout_url else None

    @property
    def media(self):
        """
        Return all media required to render this view, including forms.
        """
        media = self._get_common_media()
        media += self._get_view_media()
        media += self.get_media_assets()
        return media

    def _get_common_media(self):
        config = getattr(settings, 'ARCTIC_COMMON_MEDIA_ASSETS', [])
        media = Media()
        if 'css' in config:
            media.add_css(config['css'])
        if 'js' in config:
            media.add_js(config['js'])
        return media

    def get_media_assets(self):
        """
        Allows to define additional media for view
        """
        return Media()

    def _get_view_media(self):
        """
        Gather view-level media assets
        """
        media = Media()
        try:
            media.add_css(self.Media.css)
        except AttributeError:
            pass
        try:
            media.add_js(self.Media.js)
        except AttributeError:
            pass
        return media

    def get_form_display(self):
        valid_options = ['stacked', 'tabular', 'float-label']
        if self.form_display:
            if self.form_display in valid_options:
                return self.form_display
            raise ImproperlyConfigured(
                'form_display property needs to be one of {}'.format(
                    valid_options))
        return arctic_setting('ARCTIC_FORM_DISPLAY', valid_options)


class TemplateView(View, base.TemplateView):
    pass


class DetailView(View, base.DetailView):
    """
    Custom detail view.
    """

    fields = None            # Which fields should be shown in the details
    links = None             # Optional links such as list of linked items

    def get_fields(self, obj):
        result = OrderedDict()
        if self.fields:
            for field_name in self.fields:
                if isinstance(field_name, tuple):
                    # custom property that is not a field of the model
                    result[field_name[1]] = getattr(obj, field_name[0])
                else:
                    field = self.model._meta.get_field(field_name)
                    result[field.verbose_name.title()] = getattr(obj,
                                                                 field_name)
        return result

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        context['fields'] = self.get_fields(context['object'])
        return context


class ListView(View, ListMixin, base.ListView):
    """
    Custom listview. Adding filter, sorting and display logic.
    """
    prefix = ''  # Prefix for embedding multiple list views in detail view

    def get(self, request, *args, **kwargs):
        objects = self.get_object_list()
        context = self.get_context_data(object_list=objects)

        return self.render_to_response(context)

    def get_object_list(self):
        qs = self.get_queryset()

        if self.get_advanced_search_form():
            form = self.get_advanced_search_form()(data=self.request.GET)
            if not hasattr(form, 'get_search_filter'):
                raise AttributeError(
                    'advanced_search_form must implement get_search_filter()')
            qs = qs.filter(form.get_search_filter())

        if self.get_simple_search_form():
            if self.get_search_fields():
                form = self.get_simple_search_form()(
                    search_fields=self.get_search_fields(),
                    data=self.request.GET
                )
            else:
                form = self.get_simple_search_form()(data=self.request.GET)

            if not hasattr(form, 'get_search_filter'):
                raise AttributeError(
                    'simple_search_form must implement get_search_filter()')
            qs = qs.filter(form.get_search_filter())

        self.object_list = qs

        return self.object_list

    def get_list_header(self):
        """
        Creates a list of dictionaries with the field names, labels,
        field links, field css classes, order_url and order_direction,
        this simplifies the creation of a table in a template.
        """
        model = self.object_list.model
        result = []
        if not self.get_fields():
            result.append({
                'name': '',
                'verbose': str(model._meta.verbose_name),
            })
        else:
            prefix = self.get_prefix()
            for field_name in self.get_fields():
                item = {}
                if isinstance(field_name, tuple):
                    # custom property that is not a field of the model
                    name = field_name[0]
                    item['label'] = field_name[1]
                else:
                    name = field_name
                    try:
                        field_meta = find_field_meta(
                            model,
                            field_name
                        )
                        if field_meta._verbose_name:  # noqa
                            # explicitly set on the model, so don't change
                            item['label'] = field_meta._verbose_name  # noqa
                        else:
                            # title-case the field name (issue #80)
                            item['label'] = field_meta.verbose_name.title()
                    except FieldDoesNotExist:
                        item['label'] = field_name
                    except AttributeError:
                        item['label'] = field_name
                item['name'] = prefix + name
                if name in self.get_ordering_fields():
                    item['order_url'], item['order_direction'] = \
                        self.ordering_url(name)
                result.append(item)

        return result

    def get_list_items(self, objects):
        self.has_action_links = False
        items = []
        if not self.get_fields():
            for obj in objects:
                items.append([obj.pk, str(obj)])
            return items

        # remove all tuples in the field list, no need for the verbose
        # field name here
        fields = self.get_fields(strip_labels=True)
        field_links = self.get_field_links()
        field_classes = self.get_field_classes()
        for obj in objects:
            row = []

            for field_name in fields:
                field = {'type': 'field', 'field': field_name}
                base_field_name = field_name.split('__')[0]
                field_class = get_field_class(objects, base_field_name)
                field['value'] = self.get_field_value(field_name, obj)
                if field_class == 'ManyToManyField':
                    #  ManyToManyField will be display as an embedded list
                    #  capped to max_embeded_list_items, an ellipsis is
                    #  added if there are more items than the max.
                    m2mfield = getattr(obj, base_field_name)
                    embeded_list = list(str(l) for l in
                                        m2mfield.all()
                                        [:self.max_embeded_list_items + 1])
                    if len(embeded_list) > self.max_embeded_list_items:
                        embeded_list = embeded_list[:-1] + ['...']
                    field['value'] = embeded_list
                if field_name in field_links.keys():
                    try:
                        field['url'] = reverse_url(
                            field_links[field_name], obj, self.primary_key)
                    except NoReverseMatch:
                        pass
                if field_name in field_classes:
                    field['class'] = field_classes[field_name]
                row.append(field)
            actions = self._get_field_actions(obj)
            if actions:
                row.append(actions)
                self.has_action_links = True
            items.append(row)
        return items

    def get_field_value(self, field_name, obj):
        # first try to find a virtual field
        virtual_field_name = "get_{}_field".format(field_name)
        if hasattr(self, virtual_field_name):
            return getattr(self, virtual_field_name)(obj)
        try:
            # Get the choice display value
            parent_objs = '__'.join(
                field_name.split('__')[:-1])
            method_name = '{}__get_{}_display'.format(
                parent_objs,
                field_name.split('__')[-1]).strip('__')
            return find_attribute(obj, method_name)()
        except (AttributeError, TypeError):
            # finally get field's value
            return find_attribute(obj, field_name)

    def get_prefix(self):
        return self.prefix + '-' if self.prefix else ''

    def get_default_ordering(self):
        prefix = self.get_prefix()
        return [prefix + f for f in self.default_ordering]

    def get_ordering_with_prefix(self):
        return self.request.GET.getlist('order', self.get_default_ordering())

    def get_ordering(self):
        """Ordering used for queryset filtering (should not contain prefix)."""
        prefix = self.get_prefix()
        fields = self.get_ordering_with_prefix()
        if self.prefix:
            fields = [f.replace(prefix, '', 1) for f in fields]
        return [f for f in fields if f.lstrip('-')
                in self.get_ordering_fields()]

    def get_page_title(self):
        if not self.page_title:
            return capfirst(self.object_list.model._meta.verbose_name_plural)
        return self.page_title

    def get_context_data(self, **kwargs):
        context = super(ListView, self).get_context_data(**kwargs)
        context['prefix'] = self.prefix
        context['list_header'] = self.get_list_header()
        context['list_items'] = self.get_list_items(context['object_list'])
        context['tool_links'] = self.get_tool_links()
        # self.has_action_links is set in get_list_items
        context['has_action_links'] = self.has_action_links
        context['tool_links_icon'] = self.get_tool_links_icon()
        if self.get_simple_search_form():
            context['simple_search_form'] = \
                self.get_simple_search_form()(data=self.request.GET)
        if self.get_advanced_search_form():
            context['advanced_search_form'] = \
                self.get_advanced_search_form()(data=self.request.GET)
        return context


class DataListView(TemplateView, ListMixin):
    dataset = None
    template_name = 'arctic/base_list.html'
    page_kwarg = 'page'

    def get_ordering(self):
        return self.request.GET.get('order', '').split(',')

    def get_context_data(self, **kwargs):
        context = super(DataListView, self).get_context_data(**kwargs)
        page_size = self.get_paginate_by()
        self.dataset.page_size = page_size
        object_list = self.get_objects()
        page_context = {
            'paginator': None,
            'page_obj': None,
            'is_paginated': False,
            'object_list': object_list
        }
        if page_size:
            paginator, page, object_list, is_paginated = self.paginate_dataset(
                object_list, page_size)
            page_context = {
                'paginator': paginator,
                'page_obj': page,
                'is_paginated': is_paginated,
                'object_list': object_list
            }
        context.update(page_context)
        context['list_header'] = self.get_list_header()
        context['list_items'] = self.get_list_items(object_list)
        context['action_links'] = self.get_action_links()
        context['tool_links'] = self.get_tool_links()
        # self.has_action_links is set in get_list_items
        context['has_action_links'] = self.has_action_links
        context['tool_links_icon'] = self.get_tool_links_icon()
        if self.get_simple_search_form():
            context['simple_search_form'] = \
                self.get_simple_search_form()(data=self.request.GET)
        if self.get_advanced_search_form():
            context['advanced_search_form'] = \
                self.get_advanced_search_form()(data=self.request.GET)

        return context

    def get_paginate_by(self):
        return self.paginate_by

    def get_list_header(self):
        """
        Creates a list of dictionaries with the field names, labels,
        field links, field css classes, order_url and order_direction,
        this simplifies the creation of a table in a template.
        """
        result = []
        for field_name in self.get_fields():
            item = {}
            if isinstance(field_name, tuple):
                # custom property that is not a field of the model
                item['name'] = field_name[0]
                item['label'] = field_name[1]
            else:
                item['name'] = field_name
                item['label'] = field_name.title()
            if item['name'] in self.get_ordering_fields():
                item['order_url'], item['order_direction'] = \
                    self.ordering_url(item['name'])
            result.append(item)

        return result

    def get_objects(self):
        objects = (self.dataset
                   .fields(self.get_fields(strip_labels=False))
                   .order_by(self.get_ordering()))
        search_fields = self.get_search_fields()
        if search_fields:
            if len(search_fields) > 1:
                raise ValidationError('search_fields in DataListView currently'
                                      ' only accepts one field')
            search = {}
            for search_field in search_fields:
                value = self.request.GET.get('search', '')
                search[search_field] = value
            if search:
                objects = objects.filter(**search)
        return objects

    def get_list_items(self, objects):
        self.has_action_links = False
        items = []
        fields = []
        field_links = self.get_field_links()
        field_classes = self.get_field_classes()
        for field in self.get_fields():
            fields.append(field[0] if type(field) in (list, tuple)
                          else field)
        for obj in objects:
            row = []
            for field_name in fields:
                field = {'field': field_name, 'type': 'field'}
                field['value'] = self.get_field_value(field_name, obj)
                if field_name in field_links.keys():
                    try:
                        field['url'] = reverse_url(
                            field_links[field_name], obj, self.primary_key)
                    except NoReverseMatch:
                        pass
                if field_name in field_classes:
                    field['class'] = field_classes[field_name]
                row.append(field)
            items.append(row)
            actions = self._get_field_actions(obj)
            if actions:
                row.append(actions)
                self.has_action_links = True
        return items

    def get_field_value(self, field_name, obj):
        try:  # first try to find a virtual field
            virtual_field_name = "get_{}_field".format(field_name)
            return getattr(self, virtual_field_name)(obj)
        except AttributeError:
            try:
                return obj[field_name]
            except KeyError:
                raise FieldDoesNotExist(
                    'Field "{}" is not available'.format(field_name))

    def get_paginator(self, dataset, per_page, orphans=0,
                      allow_empty_first_page=True, **kwargs):
        """Return an instance of the paginator for this view."""
        return IndefinitePaginator(
            dataset, per_page, orphans=orphans,
            allow_empty_first_page=allow_empty_first_page, **kwargs)

    def paginate_dataset(self, dataset, page_size):
        paginator = self.get_paginator(
            dataset, page_size, orphans=0,
            allow_empty_first_page=True)
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg)\
            or 1
        try:
            page_number = int(page)
        except ValueError:
            raise Http404(_('Page cannot be converted to an int.'))
        try:
            page = paginator.page(page_number)
            return (paginator, page, page.object_list, page.has_other_pages())
        except InvalidPage as e:
            raise Http404(_('Invalid page (%(page_number)s): %(message)s') % {
                'page_number': page_number,
                'message': str(e)
            })


class CreateView(FormMediaMixin, View, SuccessMessageMixin,
                 FormMixin, extra_views.CreateWithInlinesView):
    template_name = 'arctic/base_create_update.html'
    success_message = _('%(object)s was created successfully')

    def get_page_title(self):
        if not self.page_title:
            return _("Create %s") % self.model._meta.verbose_name
        return self.page_title

    def get_context_data(self, **kwargs):
        context = super(CreateView, self).get_context_data(**kwargs)
        context['links'] = self.get_links()
        context['layout'] = self.get_layout()
        return context


class UpdateView(FormMediaMixin, SuccessMessageMixin, FormMixin, View,
                 extra_views.UpdateWithInlinesView):
    template_name = 'arctic/base_create_update.html'
    success_message = _('%(object)s was updated successfully')

    def get_page_title(self):
        if not self.page_title:
            return _("Edit %s") % self.model._meta.verbose_name
        return self.page_title

    def get_context_data(self, **kwargs):
        context = super(UpdateView, self).get_context_data(**kwargs)
        context['links'] = self.get_links()
        context['layout'] = self.get_layout()
        return context


class FormView(FormMediaMixin, View, SuccessMessageMixin, FormMixin,
               base.FormView):
    template_name = 'arctic/base_create_update.html'

    def get_context_data(self, **kwargs):
        context = super(FormView, self).get_context_data(**kwargs)
        context['links'] = self.get_links()
        context['layout'] = self.get_layout()
        return context


class DeleteView(SuccessMessageMixin, View, base.DeleteView):
    template_name = 'arctic/base_confirm_delete.html'

    def get(self, request, *args, **kwargs):
        """
        Catch protected relations and show to user.
        """
        self.object = self.get_object()
        can_delete = True
        protected_objects = []
        collector_message = None
        collector = Collector(using='default')
        try:
            collector.collect([self.object])
        except ProtectedError as e:
            collector_message = "Cannot delete %s because it has relations " \
                                "that depends on it." % self.object
            protected_objects = e.protected_objects
            can_delete = False

        context = self.get_context_data(object=self.object,
                                        can_delete=can_delete,
                                        collector_message=collector_message,
                                        protected_objects=protected_objects)
        return self.render_to_response(context)


class LoginView(FormView):
    template_name = 'arctic/login.html'
    page_title = 'Login'
    requires_login = False
    form_class = AuthenticationForm

    def __init__(self, *args, **kwargs):
        super(LoginView, self).__init__(*args, **kwargs)
        # thread-safe definition of messages.
        self.messages = []

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(LoginView, self).get_context_data(**kwargs)
        context['next'] = self.request.GET.get('next', '/')
        context['username'] = self.request.POST.get('username', '')
        context['messages'] = set(self.messages)
        return context

    def get(self, request, *args, **kwargs):
        logout(request)
        return super(LoginView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = authenticate(username=request.POST['username'],
                            password=request.POST['password'])
        if user and user.is_active:
            login(request, user)

            next_url = request.GET.get('next')
            if is_safe_url(next_url, request.get_host()):
                return redirect(next_url)

            return redirect('/')

        self.messages.append('Invalid username/password combination')

        return render(request, self.template_name,
                      self.get_context_data(**kwargs))
