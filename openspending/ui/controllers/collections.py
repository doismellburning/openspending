import logging
import colander

from pylons import request, response, tmpl_context as c, session
from pylons.controllers.util import abort, redirect
from pylons.i18n import _

from openspending.ui.lib.base import BaseController, render
from openspending.ui.lib.views import handle_request
from openspending.ui.lib.browser import Browser
from openspending.lib.csvexport import write_csv
from openspending.lib.jsonexport import to_jsonp
from openspending.ui.lib import helpers as h
from openspending.ui.lib.base import require
from openspending.model import meta as db

from openspending import model
from openspending.model.entry_collection import EntryCollectionCreate

log = logging.getLogger(__name__)

class CollectionsController(BaseController):

    def create(self, dataset):
        require.account.create()
        self._get_dataset(dataset)

        c.entry_list = request.params['entry_list'].split(',')
        c.return_url = request.params['return_url']

        try:
            schema = EntryCollectionCreate()
            values = request.params
            data = schema.deserialize(values)
            if c.dataset.entry_collection.by_name(data['name']):
                raise colander.Invalid(
                    EntryCollectionCreate.name,
                    _("Collection name already exists, please choose a "
                      "different one"))
            c.collection = c.dataset.entry_collection(data['name'])
            c.collection.label = data['label']
            c.collection.description = data['description']
            db.session.add(c.collection)

            session['current_collection'] = c.collection.id
            session.save()

            h.flash_success(_("Created collection %s.") % c.collection.name)

            self._add_to_collection()

            db.session.commit()

            if len(c.return_url):
                redirect(c.return_url)
            else:
                redirect(h.url_for(controller='dataset', action='view', 
                                   dataset=c.dataset.name))

        except colander.Invalid, i:
            errors = i.asdict()
            log.debug(errors)
            return render('collection/new.html', form_fill=values, form_errors=errors)
