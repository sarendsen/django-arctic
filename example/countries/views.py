from __future__ import (absolute_import, unicode_literals)

import json
from six.moves import urllib

from django.utils.safestring import mark_safe

from arctic.generics import DataListView
from arctic.utils import RemoteDataSet


class CountriesDataSet(RemoteDataSet):
    # url_template = 'https://restcountries.eu/rest/v2{filters}'
    url_template = 'http://api.staging.autoweek.nl/v1/occasions/?format=json{filters}{order}'
    filters_template_kv = '/{key}/{value}'

    def get(self, page, paginate_by):
        print(self.get_url(page, paginate_by))
        r = urllib.request.urlopen((self.get_url(page, paginate_by)))
        offset = (page - 1) * paginate_by
        limit = offset + paginate_by
        data = r.read().decode("utf-8")
        return json.loads(data).get('occasions', [])[offset:limit]

    def order_params(self):
        """
        Convert current ordering values to GET params for the REST API.
        For example [('name', DESC)] to {'ascending': 1, 'sort': 'mileage']}
        This endpoint supports ordering by one field only.
        """
        params = {}
        mapping = {
            "price": "price_public",
            "mileage": "mileage",
        }
        if self.order_values:
            field, order_type = self.order_values[0]
            if order_type == self.DESC:
                params['ascending'] = 1
            params['sort'] = mapping.get(field, 'price_public')
        return params

    def __len__(self):
        return len(self.get(1, -1))


class CountryListView(DataListView):
    paginate_by = 5
    dataset = CountriesDataSet()
    # fields = ['name', 'topLevelDomain', 'capital', 'flag']
    fields = ('name', 'media', 'mileage', 'price', 'fuel', 'transmission')
    ordering_fields = ['mileage', 'price']
    search_fields = ['name', 'price']
    breadcrumbs = (('Home', 'index'), ('Country List', None))
    filter_fields = ['fuel' 'transmission']
    permission_required = 'country_view'

    def get_media_field(self, obj):
        return mark_safe('<div style="width: 3em;"><img src="{}" /></div>'.
                         format(obj['media']['thumbnail']))

    def get_name_field(self, obj):
        return mark_safe('<div>'
                         '<a href="http://api.staging.autoweek.nl/{}" target="_blank"/>'
                         '{}</a></div>'.
                         format(obj['url'], obj['name']))
