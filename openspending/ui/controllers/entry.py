import logging

from pylons import request, response, tmpl_context as c, session
from pylons.controllers.util import abort, redirect
from pylons.i18n import _

from openspending.plugins.core import PluginImplementations
from openspending.plugins.interfaces import IEntryController
from openspending.ui.lib.base import BaseController, render
from openspending.ui.lib.views import handle_request
from openspending.ui.lib.browser import Browser
from openspending.lib.csvexport import write_csv
from openspending.lib.jsonexport import to_jsonp
from openspending.ui.lib import helpers as h

from openspending.model import meta as db

log = logging.getLogger(__name__)

class EntryController(BaseController):

    extensions = PluginImplementations(IEntryController)
    
    def index(self, dataset, format='html'):
        self._get_dataset(dataset)
        self._get_collections()
        handle_request(request, c, c.dataset)
        url = h.url_for(controller='entry', action='index',
                    dataset=c.dataset.name)
        c.browser = Browser(c.dataset, request.params, url=url)
        c.browser.facet_by_dimensions()

        if format == 'json':
            response.content_disposition = 'attachment; filename=%s.json' % c.dataset.name
            return c.browser.to_jsonp()
        elif format == 'csv':
            response.content_disposition = 'attachment; filename=%s.csv' % c.dataset.name
            return c.browser.to_csv()
        else:
            return render('entry/index.html')

    def view(self, dataset, id, format='html'):
        self._get_dataset(dataset)
        self._get_collections()
        entries = list(c.dataset.entries(c.dataset.alias.c.id==id))
        if not len(entries) == 1:
            abort(404, _('Sorry, there is no entry %r') % id)
        c.entry = entries.pop()

        c.id = c.entry.get('id')
        c.from_ = c.entry.get('from')
        c.to = c.entry.get('to')
        c.currency = c.entry.get('currency', c.dataset.currency).upper()
        c.amount = c.entry.get('amount')
        c.time = c.entry.get('time')

        c.custom_html = h.render_entry_custom_html(c.dataset, 
                                                   c.entry)

        excluded_keys = ('time', 'amount', 'currency', 'from',
                         'to', 'dataset', 'id', 'name', 'description')

        c.extras = {}
        if c.dataset:
            c.desc = dict([(d.name, d) for d in c.dataset.dimensions])
            for key in c.entry:
                if key in c.desc and \
                        not key in excluded_keys:
                    c.extras[key] = c.entry[key]

        for item in self.extensions:
            item.read(c, request, response, c.entry)

        if format == 'json':
            return to_jsonp(c.entry)
        elif format == 'csv':
            return write_csv([c.entry], response)
        else:
            return render('entry/view.html')

    def collect(self, dataset, id):
        self._get_dataset(dataset)

        c.entry_list = [id]
        c.return_url = request.params['return_url']

        r = self._get_collection_for_add()
        if r is not None:
            return r

        self._add_to_collection()
        db.session.commit()

        redirect(c.return_url)

    def collect_list(self, dataset):
        self._get_dataset(dataset)

        c.entry_list = request.params.getall('entry_select')
        c.return_url = request.params['return_url']

        r = self._get_collection_for_add()
        if r is not None:
            return r

        self._add_to_collection()
        db.session.commit()

        redirect(c.return_url)
