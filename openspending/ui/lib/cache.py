from sys import maxint
import math
import hashlib
import logging

from paste.deploy.converters import asbool
from pylons import cache, config

log = logging.getLogger(__name__)

class QueryCache(object):
    """ A proxy object to run cached calls against the dataset 
    select function. This is neither a concern of the data 
    model itself, nor should it be repeated at each location 
    where caching of aggreagtes should occur - thus it ends up 
    here. """

    def __init__(self, dataset, type='dbm'):
        self.dataset = dataset
        opt = config.get('openspending.cache_enabled', 'True')
        self.cache_enabled = asbool(opt) and \
                not self.dataset.private
        self.cache = cache.get_cache('DSCACHE_' + dataset.name,
                                     type=type)
        
    def select(self, measure='amount', with_fields=None, cuts=None, slice=None,
               from_collection=None,
               page=1, pagesize=10000, order=None, aggregate=False):
        """ For call docs, see ``model.Dataset.select``. """

        if not self.cache_enabled:
            log.debug("Caching is disabled.")
            return self.dataset.select(measure=measure,
                                       with_fields=with_fields,
                                       cuts=cuts, slice=slice,
                                       from_collection=from_collection,
                                       page=page,
                                       pagesize=pagesize,
                                       order=order,
                                       aggregate=aggregate)

        key_parts = {'m': measure,
                     'd': sorted(with_fields or []),
                     'f': from_collection,
                     'c': sorted(cuts or []),
                     's': sorted(map(sorted, slice or [])),
                     'o': order,
                     'a': aggregate}
        key = hashlib.sha1(repr(key_parts)).hexdigest()

        if self.cache.has_key(key):
            log.debug("Cache hit: %s", key)
            r = self.cache.get(key)
        else:
            log.debug("Generating: %s", key)
            # Note that we're not passing pagination options. Since
            # the computational effort of giving a page is the same
            # as returning all, we're taking the network hit and 
            # storing the full result set in all cases.
            r = self.dataset.select(measure=measure,
                                    with_fields=with_fields,
                                    cuts=cuts,
                                    slice=slice,
                                    from_collection=from_collection,
                                    page=1,
                                    pagesize=maxint,
                                    order=order,
                                    aggregate=aggregate)
            self.cache.put(key, r)

        # Restore pagination by splicing the cached result.
        offset = ((page-1)*pagesize)
        results = r['result']
        r['summary']['cached'] = True
        r['summary']['cache_key'] = key
        r['summary']['num_results'] = len(results)
        r['summary']['page'] = page
        r['summary']['pages'] = int(math.ceil(len(results)/float(pagesize)))
        r['summary']['pagesize'] = pagesize
        r['result'] = results[offset:offset+pagesize]
        return r

    def invalidate(self):
        """ Clear the cache. """
        self.cache.clear()

class AggregationCache(QueryCache):
    """ Compatibility with existing callers of aggregate """

    def aggregate(self, **kwargs):
        """ For call docs, see ``model.Dataset.aggregate``. """

        kwargs['with_fields'] = kwargs.pop('drilldowns')

        r = self.select(aggregate=True, **kwargs)
        r['summary']['num_drilldowns'] = r['summary']['num_results']
        r['drilldown'] = r['result']
        del r['summary']['num_results']
        del r['result']
        return r
