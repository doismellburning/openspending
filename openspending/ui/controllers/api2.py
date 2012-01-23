import logging
import re

from pylons import request, response
from pylons.controllers.util import etag_cache

from openspending import model
from openspending.lib.jsonexport import jsonpify
from openspending.ui.lib.base import BaseController, require
from openspending.ui.lib.cache import QueryCache

log = logging.getLogger(__name__)

class Api2Controller(BaseController):

    @jsonpify
    def select(self):
        return self._select()

    @jsonpify
    def aggregate(self):
        r = self._select(aggregate=True)
        r['summary']['num_drilldowns'] = r['summary']['num_results']
        r['drilldown'] = r['result']
        del r['summary']['num_results']
        del r['result']
        return r

    def _select(self, aggregate=False):
        errors = []
        params = request.params

        # get and check parameters
        dataset = self._dataset(params, errors)
        if aggregate:
            with_fields = self._drilldowns(params, errors)
        else:
            with_fields = self._fields(params, errors)
        cuts = self._cuts(params, errors)
        slice = self._slice(params, errors)
        collection = self._from_collection(params, dataset, errors)
        order = self._order(params, errors)
        measure = self._measure(params, dataset, errors)
        page = self._to_int('page', params.get('page', 1), errors)
        pagesize = self._to_int('pagesize', params.get('pagesize', 10000),
                                errors)
        if errors:
            return {'errors': errors}

        try:
            cache = QueryCache(dataset)
            result = cache.select(measure=measure, 
                                  with_fields=with_fields,
                                  cuts=cuts, slice=slice,
                                  from_collection=collection,
                                  page=page, pagesize=pagesize,
                                  order=order, aggregate=aggregate)

            if cache.cache_enabled and 'cache_key' in result['summary']:
                if 'Pragma' in response.headers:
                    del response.headers['Pragma']
                response.cache_control = 'public; max-age: 84600'
                etag_cache(result['summary']['cache_key'])

        except (KeyError, ValueError) as ve:
            log.exception(ve)
            return {'errors': ['Invalid aggregation query: %r' % ve]}

        return result

    @jsonpify
    def collect(self):
        errors = []
        params = request.params

        # get and check parameters
        dataset = self._dataset(params, errors)
        cuts = self._cuts(params, errors)
        slice = self._slice(params, errors)
        collection = self._to_collection(params, dataset, errors)

        if errors:
            return {'errors': errors}

        try:
            result = dataset.collect(collection_id, cuts=cuts, slice=slice)
            db.session.commit()

        except (KeyError, ValueError) as ve:
            log.exception(ve)
            return {'errors': ['Invalid query: %r' % ve]}

        return result

    def _dataset(self, params, errors):
        dataset_name = params.get('dataset')
        dataset = model.Dataset.by_name(dataset_name)
        if dataset is None:
            errors.append('no dataset with name "%s"' % dataset_name)
            return
        require.dataset.read(dataset)
        return dataset

    def _measure(self, params, dataset, errors):
        if dataset is None:
            return
        name = params.get('measure', 'amount')
        for measure in dataset.measures:
            if measure.name == name:
                return name
        errors.append('no measure with name "%s"' % name)

    def _from_collection(self, params, dataset, errors):
        if dataset is None:
            return
        name = params.get('from_collection')
        collection = dataset.entry_collection.by_name(name)
        return collection

    def _to_collection(self, params, dataset, errors):
        if dataset is None:
            return
        name = params.get('to_collection')

        if db.session.query().filter(dataset.entry_collection.name == name).count() > 0:
            # This could be permitted - there's no underlying issue
            # with appending to a collection - but let's leave it out
            # until we think it's a good idea
            errors.append('collection with name "%s" already exists' % name)
        else:
            collection = dataset.entry_collection(name)
            db.session.add(collection)
            return collection

    def _drilldowns(self, params, errors):
        drilldown_param = params.get('drilldown', None)
        if drilldown_param is None:
            return []
        return drilldown_param.split('|')

    def _fields(self, params, errors):
        fields_param = params.get('fields', None)
        if fields_param is None:
            return []
        return fields_param.split('|')

    def _cuts(self, params, errors):
        cut_param = params.get('cut', None)

        if cut_param is None:
            return []

        cuts = cut_param.split('|')
        result = []
        for cut in cuts:
            try:
                (dimension, value) = cut.split(':')
            except ValueError:
                errors.append('Wrong format for "cut". It has to be specified '
                              'with request cut_parameters in the form '
                              '"cut=dimension:value|dimension:value". '
                              'We got: "cut=%s"' %
                              cut_param)
                return
            else:
                #try:
                #    value = float(value)
                #except:
                #    pass
                result.append((dimension, value))
        return result

    slice_term_pattern = re.compile(r'^(.*?)(:|!|<|>|<:|>:)(.*)$')

    def _slice(self, params, errors):
        slice_param = params.get('slice', None)

        if slice_param is None:
            return None

        conjs = slice_param.split('|')
        result = []
        for conj in conjs:
            terms = conj.split('*')
            conj_result = []
            for term in terms:
                m = Api2Controller.slice_term_pattern.match(term)
                if m is None:
                    errors.append('Wrong format for "slice". '
                                  'We could not understand the term "%s" '
                                  'in "%s"' %
                                  (term, slice_param)
                                  )
                    return
                conj_result.append(m.groups())
            result.append(conj_result)
        return result

    def _order(self, params, errors):
        order_param = params.get('order', None)

        if order_param is None:
            return []

        parts = order_param.split('|')
        result = []
        for part in parts:
            try:
                (dimension, direction) = part.split(':')
            except ValueError:
                errors.append(
                    'Wrong format for "order". It has to be '
                    'specified with request parameters in the form '
                    '"order=dimension:direction|dimension:direction". '
                    'We got: "order=%s"' % order_param)
            else:
                if direction not in ('asc', 'desc'):
                    errors.append('Order direction can be "asc" or "desc". We '
                                  'got "%s" in "order=%s"' %
                                  (direction, order_param))
                    continue
                if direction == 'asc':
                    reverse = False
                else:
                    reverse = True
                result.append((dimension, reverse))
        return result

    def _to_int(self, key, value, errors):
        try:
            return int(value)
        except ValueError:
            errors.append('"%s" has to be an integer, it is: %s' % str(value))
