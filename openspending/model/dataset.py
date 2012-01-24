"""
The ``Dataset`` serves as double function in OpenSpending: on one hand, it is
a simple domain object that can be created, modified and deleted as any other
On the other hand it serves as a controller object for the dataset-specific
data model which it represents, handling the creation, filling and migration of
the table schema associated with the dataset. As such, it holds the key set
of logic functions upon which all other queries and loading functions rely.
"""
import math
import logging
from collections import defaultdict
from datetime import datetime
from itertools import count

from openspending.model import meta as db
from openspending.lib.util import hash_values

from openspending.model.common import TableHandler, JSONType, InsertFromSelect, \
        ALIAS_PLACEHOLDER
from openspending.model.dimension import CompoundDimension, \
        AttributeDimension, DateDimension
from openspending.model.dimension import Measure
from openspending.model.entry_collection import make_entry_collection_classes

log = logging.getLogger(__name__)

class Dataset(TableHandler, db.Model):
    """ The dataset is the core entity of any access to data. All
    requests to the actual data store are routed through it, as well
    as data loading and model generation.

    The dataset keeps an in-memory representation of the data model
    (including all dimensions and measures) which can be used to 
    generate necessary queries.
    """
    __tablename__ = 'dataset'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(255), unique=True)
    label = db.Column(db.Unicode(2000))
    description = db.Column(db.Unicode())
    currency = db.Column(db.Unicode())
    default_time = db.Column(db.Unicode())
    schema_version = db.Column(db.Unicode())
    entry_custom_html = db.Column(db.Unicode())
    ckan_uri = db.Column(db.Unicode())
    private = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    data = db.Column(JSONType, default=dict)

    languages = db.association_proxy('_languages', 'code')
    territories = db.association_proxy('_territories', 'code')

    def __init__(self, data):
        self.data = data.copy()
        dataset = self.data['dataset']
        del self.data['dataset']
        self.label = dataset.get('label')
        self.name = dataset.get('name')
        self.description = dataset.get('description')
        self.currency = dataset.get('currency')
        self.default_time = dataset.get('default_time')
        self.entry_custom_html = dataset.get('entry_custom_html')
        self.languages = dataset.get('languages', [])
        self.territories = dataset.get('territories', [])
        self.ckan_uri = dataset.get('ckan_uri')
        self._load_model()

    @property
    def model(self):
        model = self.data.copy()
        model['dataset'] = self.as_dict()
        return model

    @property
    def mapping(self):
        return self.data.get('mapping', {})

    @db.reconstructor
    def _load_model(self):
        """ Construct the in-memory object representation of this
        dataset's dimension and measures model.

        This is called upon initialization and deserialization of
        the dataset from the SQLAlchemy store.
        """
        self.dimensions = []
        self.measures = []
        for dim, data in self.mapping.items():
            if data.get('type') == 'measure' or dim == 'amount':
                self.measures.append(Measure(self, dim, data))
                continue
            elif data.get('type') == 'date' or \
                (dim == 'time' and data.get('datatype') == 'date'):
                dimension = DateDimension(self, dim, data)
            elif data.get('type') in ['value', 'attribute']:
                dimension = AttributeDimension(self, dim, data)
            else:
                dimension = CompoundDimension(self, dim, data)
            self.dimensions.append(dimension)
        self.init()
        self._is_generated = None

    def __getitem__(self, name):
        """ Access a field (dimension or measure) by name. """
        for field in self.fields:
            if field.name == name:
                return field
        raise KeyError()

    @property
    def fields(self):
        """ Both the dimensions and metrics in this dataset. """
        return self.dimensions + self.measures

    @property
    def compounds(self):
        """ Return only compound dimensions. """
        return filter(lambda d: isinstance(d, CompoundDimension),
                self.dimensions)

    def init(self):
        """ Create a SQLAlchemy model for the current dataset model, 
        without creating the tables and columns. This needs to be 
        called both for access to the data and in order to generate
        the model physically. """
        self.bind = db.engine #.connect()
        self.meta = db.MetaData()
        #self.tx = self.bind.begin()
        self.meta.bind = db.engine
        declarative = db.declarative_base(bind=self.bind, metadata=self.meta)

        self._init_table(self.meta, self.name, 'entry',
                         id_type=db.Unicode(42))
        for field in self.fields:
            field.init(self.meta, self.table)
        self.alias = self.table.alias('entry')

        self.entry_collection, self.entry_collection_entry = make_entry_collection_classes(self.name,
                                                                                           declarative,
                                                                                           self.table)

    def generate(self):
        """ Create the tables and columns necessary for this dataset
        to keep data.
        """
        for field in self.fields:
            field.generate(self.meta, self.table)
        self._generate_table()

        # Not really sure if the above is needed. Certainly MetaData
        # can sort out the collections tables without our help
        self.meta.create_all()
        
        self._is_generated = True

    @property
    def is_generated(self):
        if self._is_generated is None:
            self._is_generated = self.table.exists()
        return self._is_generated

    def commit(self):
        pass
        #self.tx.commit()
        #self.tx = self.bind.begin()

    def _make_key(self, data):
        """ Generate a unique identifier for an entry. This is better 
        than SQL auto-increment because it is stable across mutltiple
        loads and thus creates stable URIs for entries. 
        """
        uniques = [self.name]
        for field in self.fields:
            if not field.key:
                continue
            obj = data.get(field.name)
            if isinstance(obj, dict):
                obj = obj.get('name', obj.get('id'))
            uniques.append(obj)
        return hash_values(uniques)

    def load(self, data):
        """ Handle a single entry of data in the mapping source format, 
        i.e. with all needed columns. This will propagate to all dimensions
        and set values as appropriate. """
        entry = dict()
        for field in self.fields:
            field_data = data[field.name]
            entry.update(field.load(self.bind, field_data))
        entry['id'] = self._make_key(data)
        self._upsert(self.bind, entry, ['id'])

    def flush(self):
        """ Delete all data from the dataset tables but leave the table
        structure intact.
        """
        for dimension in self.dimensions:
            dimension.flush(self.bind)
        self.bind.execute(db.delete(self.entry_collection.__table__))
        self.bind.execute(db.delete(self.entry_collection_entry.__table__))
        self._flush(self.bind)

    def drop(self):
        """ Drop all tables created as part of this dataset, i.e. by calling
        ``generate()``. This will of course also delete the data itself.
        """
        for dimension in self.dimensions:
            dimension.drop(self.bind)

        self.meta.drop_all(tables=[x.__table__ for x in self.entry_collection, self.entry_collection_entry])
            
        self._drop(self.bind)

    def key(self, key):
        """ For a given ``key``, find a column to indentify it in a query.
        A ``key`` is either the name of a simple attribute (e.g. ``time``)
        or of an attribute of a complex dimension (e.g. ``to.label``). The
        returned key is using an alias, so it can be used in a query 
        directly. """
        attr = None
        if '.' in key:
            key, attr = key.split('.', 1)
        dimension = self[key]
        if hasattr(dimension, 'alias'):
            attr_name = dimension[attr].column.name if attr else 'name'
            return dimension.alias.c[attr_name]
        return self.alias.c[dimension.column.name]

    def entries(self, conditions="1=1", order_by=None, limit=None,
            offset=0, step=10000):
        """ Generate a fully denormalized view of the entries on this 
        table. This view is nested so that each dimension will be a hash
        of its attributes. 

        This is somewhat similar to the entries collection in the fully
        denormalized schema before OpenSpending 0.11 (MongoDB).
        """
        if not self.is_generated:
            return

        joins = self.alias
        for d in self.dimensions:
            joins = d.join(joins)
        selects = [f.selectable for f in self.fields] + [self.alias.c.id]

        # enforce stable sorting:
        if order_by is None:
            order_by = [self.alias.c.id.asc()]

        for i in count():
            qoffset = offset + (step * i)
            qlimit = step
            if limit is not None:
                qlimit = min(limit-(step*i), step)
            if qlimit <= 0:
                break

            query = db.select(selects, conditions, joins, order_by=order_by,
                              use_labels=True, limit=qlimit, offset=qoffset)
            rp = self.bind.execute(query)

            first_row = True
            while True:
                row = rp.fetchone()
                if row is None:
                    if first_row:
                        return
                    break
                first_row = False
                result = {}
                for k, v in row.items():
                    field, attr = k.split('_', 1)
                    field = field.replace(ALIAS_PLACEHOLDER, '_')
                    if field == 'entry':
                        result[attr] = v
                    else:
                        if not field in result:
                            result[field] = dict()

                            # TODO: backwards-compat?
                            if isinstance(self[field], CompoundDimension):
                                result[field]['taxonomy'] = self[field].taxonomy
                        result[field][attr] = v
                yield result

    # Helper methods for basic collection CRUD
    
    def add_to_collection(self, collection, entry_id):
        x = self.entry_collection_entry(collection, entry_id)
        db.session.add(x)
        return x

    def find_in_collection(self, collection, entry_id):
        return db.query(self.entry_collection_entry).\
               filter(self.entry_collection_entry.collection_id == collection.id).\
               filter(self.entry_collection_entry.entry_id == entry_id).\
               first()

    def remove_from_collection(self, collection, entry_id):
        x = self.find_in_collection(collection, entry_id)
        db.session.delete(x)

    def collect(self, collection, cuts=None, slice=None, from_collection=None):
        """API wrapper for the parameters that are meaningful when populating a collection"""
        return self.select(cuts=cuts,
                           slice=slice,
                           from_collection=from_collection,
                           into_collection=collection)

    def _collection_entries_query(self, collection):
        # Construct a select query that returns all the entry ids in a
        # collection - convenient for constructing complex queries
        return db.select([self.entry_collection_entry.entry_id.label('id')],
                          self.entry_collection_entry.collection_id == collection.id)

    def select(self, measure='amount', with_fields=None, cuts=None, slice=None,
               from_collection=None, into_collection=None,
               page=1, pagesize=10000, order=None, aggregate=False):
        """
        See `aggregate` for detailed documentation

        ``aggregate=True``
        
            Use with_fields as the dimensions to aggregate over. If
            this is empty, aggregate over the entire dataset

        ``aggregate=False``

            Include dimensions named in with_fields in the result of
            the query, along with the row id and amount

        ``into_collection``

            Instead of returning a slice of the results, they are
            inserted into the given collection. ``with_fields`` and
            ``aggregate`` are ignored when this options is specified.

        """

        # Make sure serials are allocated before we begin
        db.session.flush()
        
        cuts = cuts or []
        with_fields = with_fields or []
        order = order or []
        joins = self.alias

        fields = set()

        # Magic aliases that can be used
        labels = {
            'year': {'join_table': 'time', 'field': self['time']['year'].column_alias.label('year')},
            'month': {'join_table': 'time', 'field': self['time']['yearmonth'].column_alias.label('month')},
            'id': {'join_table': None, 'field': self.alias.c.id.label("id")},
            }

        # Dimensions are used for grouping
        dimensions = set(with_fields + [k for k,v in cuts] + [o[0] for o in order])

        # Keep track of the things we might need to join in
        fields_to_join = dimensions.copy()

        # Put all elements of dimensions into group_by and fields,
        # mangling data types as needed
        group_by = []
        for key in dimensions:
            if key in labels:
                column = labels[key]['field']
                group_by.append(column)
                fields.add(column)
            else:
                column = self.key(key)
                if '.' in key or column.table == self.alias:
                    fields.add(column)
                    group_by.append(column)
                else:
                    fields.add(column.table)
                    for col in column.table.columns:
                        group_by.append(col)

        conditions = db.and_()
        # cut handling - simple where selection
        filters = defaultdict(set)
        for key, value in cuts:
            if key in labels:
                column = labels[key]['field']
            else:
                column = self.key(key)
            filters[column].add(value)
        for attr, values in filters.items():
            conditions.append(db.or_(*[attr==v for v in values]))

        # slice handling - generalised where selection
        if slice is not None:
            slice_disj = db.or_()
            for conj in slice:
                slice_conj = db.and_()
                for key, op, value in conj:
                    if key in labels:
                        column = labels[key]['field']
                    else:
                        column = self.key(key)
                        
                    if op == ':':
                        filter = column==value
                    elif op == '!':
                        filter = column!=value
                    elif op == '>':
                        filter = column>value
                    elif op == '<':
                        filter = column<value
                    elif op == '>:':
                        filter = column>=value
                    elif op == '<:':
                        filter = column<=value
                    else:
                        # Ignore gibberish
                        continue

                    # We already have the measure in there, possibly as a sum
                    if key != measure:
                        fields.add(column)
                        fields_to_join.add(key)
                    slice_conj.append(filter)
                slice_disj.append(slice_conj)
            conditions.append(slice_disj)

        # from_collection handling
        if from_collection is not None:
            collection_query = self._collection_entries_query(from_collection)
            conditions.append(self.alias.c.id.in_(collection_query))

        order_by = []
        for key, direction in order:
            if key in labels:
                column = labels[key]['field']
            else:
                column = self.key(key)
            order_by.append(column.desc() if direction else column.asc())

        # Compute needed joins
        for field in fields_to_join:
            if field in labels:
                table_name = labels[field]['join_table']
            else:
                table_name = str(field).split('.')[0]
            if table_name is None:
                continue
            if table_name not in [c.table.name for c in joins.columns]:
                joins = self[table_name].join(joins)

        # Add the extra fields as needed (after computing joins, because these are a bit too magic)
        if into_collection is not None:
            fields = [self.alias.c.id.label('entry_id'), db.literal(into_collection.id).label('collection_id')]
            group_by = None
            order_by = [fields[0].asc()]
        elif aggregate:
            fields.add(db.func.sum(self.alias.c[measure]).label(measure))
            fields.add(db.func.count(self.alias.c.id).label("entries"))
        else:
            fields.add(self.alias.c.id.label("id"))
            fields.add(self.alias.c[measure].label(measure))
            # For non-aggregated queries, don't do any grouping
            group_by = None

        query = db.select(list(fields), conditions, joins,
                       order_by=order_by or [measure + ' desc'],
                       group_by=group_by, use_labels=True)

        if into_collection is not None:
            # Remove all entries that are already in the collection
            collection_query = self._collection_entries_query(into_collection)
            conditions.append(db.not_(self.alias.c.id.in_(collection_query)))

            # Insert the result set into the collection
            query = InsertFromSelect(self.entry_collection_entry.__table__, query)
            rs = self.bind.execute(query)
            summary = {'num_results': rs.rowcount}
            return {'summary': summary}

        summary = {measure: 0.0, 'num_entries': 0}
        results = []
        rp = self.bind.execute(query)
        while True:
            row = rp.fetchone()
            if row is None:
                break
            result = {}
            for key, value in row.items():
                if key == measure:
                    summary[measure] += value or 0
                if key == 'entries':
                    summary['num_entries'] += value or 0
                if '_' in key:
                    dimension, attribute = key.split('_', 1)
                    dimension = dimension.replace(ALIAS_PLACEHOLDER, '_')
                    if dimension == 'entry':
                        result[attribute] = value
                    else:
                        if not dimension in result:
                            result[dimension] = {}

                            # TODO: backwards-compat?
                            if isinstance(self[dimension], CompoundDimension):
                                result[dimension]['taxonomy'] = \
                                        self[dimension].taxonomy
                        result[dimension][attribute] = value
                else:
                    if key == 'entries':
                        key = 'num_entries'
                    result[key] = value
            results.append(result)
        offset = ((page-1)*pagesize)

        # do we really need all this:
        summary['num_results'] = len(results)
        summary['page'] = page
        summary['pages'] = int(math.ceil(len(results)/float(pagesize)))
        summary['pagesize'] = pagesize

        return {'result': results[offset:offset+pagesize],
                'summary': summary}

    def aggregate(self, **kwargs):
        """ Query the dataset for a subset of cells based on cuts and 
        drilldowns. It returns a structure with a list of drilldown items 
        and a summary about the slice cutted by the query.

        ``measure``
            The numeric unit to be aggregated over, defaults to ``amount``.
        ``drilldowns``
            Dimensions to drill down to. (type: `list`)
        ``cuts``
            Specification what to cut from the cube. This is a
            `list` of `two-tuples` where the first item is the dimension
            and the second item is the value to cut from. It is turned into
            a query where multible cuts for the same dimension are combined
            to an *OR* query and then the queries for the different
            dimensions are combined to an *AND* query.
        ``slice``
            Specification of a DNF expression to filter the
            results. This is a list of lists of 3-tuples, where the
            outer list represents an OR expression, the inner list
            represents an AND expression, and each 3-tuple is of the
            form ``(dimension, op, value)``. ``op`` may be any of:

            - ``:`` equal
            - ``!`` not equal
            - ``>`` ``<`` greater/less
            - ``>:`` ``<:`` greater/less or equal

            If both ``cuts`` and ``slice`` are present, the result
            will be all cells that match both filters
        ``page``
            Page the drilldown result and return page number *page*.
            type: `int`
        ``pagesize``
            Page the drilldown result into page of size *pagesize*.
            type: `int`
        ``order``
            Sort the result based on the dimension *sort_dimension*.
            This may be `None` (*default*) or a `list` of two-`tuples`
            where the first element is the *dimension* and the second
            element is the order (`False` for ascending, `True` for
            descending).
            Type: `list` of two-`tuples`.

        Raises:

        :exc:`ValueError`
            If a cube is not yet computed. Call :meth:`compute` to compute 
            the cube.
        :exc:`KeyError`
            If a drilldown, cut or order dimension is not part of this
            cube or the order dimensions are not a subset of the drilldown
            dimensions.

        Returns: A `dict` containing the drilldown and the summary::

          {"drilldown": [
              {"num_entries": 5545,
               "amount": 41087379002.0,
               "cofog1": {"description": "",
                          "label": "Economic affairs"}},
              ... ]
           "summary": {"amount": 7353306450299.0,
                       "num_entries": 133612}}

        """
        kwargs.pop('aggregate', None)
        with_fields = kwargs.pop('drilldowns', None)
           
        r = self.select(aggregate=True, with_fields=with_fields, **kwargs)
        # Map output names
        r['summary']['num_drilldowns'] = r['summary']['num_results']
        r['drilldown'] = r['result']
        del r['summary']['num_results']
        del r['result']
        return r

    def __repr__(self):
        return "<Dataset(%s:%s:%s)>" % (self.name, self.dimensions,
                self.measures)

    def times(self, attribute='year'):
        """ Get all distinct times mentioned in the dataset. """
        # TODO: make this a more generic distinct_attribute function
        field = self['time'][attribute].column_alias
        query = db.select([field.label(attribute)], self['time'].alias, distinct=True)
        rp = self.bind.execute(query)
        return sorted([r[attribute] for r in rp.fetchall()])

    def __len__(self):
        if not self.is_generated:
            return 0
        rp = self.bind.execute(self.alias.count())
        return rp.fetchone()[0]

    def as_dict(self):
        return {
            'label': self.label,
            'name': self.name,
            'description': self.description,
            'default_time': self.default_time,
            'schema_version': self.schema_version,
            'currency': self.currency,
            'languages': list(self.languages),
            'territories': list(self.territories)
            }

    @classmethod
    def all_by_account(cls, account):
        """ Query available datasets based on dataset visibility. """
        criteria = [cls.private==False]
        if account is not None:
            criteria += ["1=1" if account.admin else "1=2",
                         cls.managers.any(type(account).id==account.id)]
        q = db.session.query(cls).filter(db.or_(*criteria))
        q= q.order_by(cls.label.asc())
        return q

    @classmethod
    def by_name(cls, name):
        return db.session.query(cls).filter_by(name=name).first()
