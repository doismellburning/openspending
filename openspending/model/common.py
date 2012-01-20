#coding: utf-8
from json import dumps, loads
from sqlalchemy.types import Text, MutableType, TypeDecorator
from sqlalchemy.sql.expression import UpdateBase, ClauseElement
from sqlalchemy.ext import compiler

from openspending.model import meta as db 

ALIAS_PLACEHOLDER = u'‽'

class JSONType(MutableType, TypeDecorator):
    impl = Text

    def __init__(self):
        super(JSONType, self).__init__()

    def process_bind_param(self, value, dialect):
        return dumps(value)

    def process_result_value(self, value, dialiect):
        return loads(value)

    def copy_value(self, value):
        return loads(dumps(value))


class TableHandler(object):
    """ Used by automatically generated objects such as datasets
    and dimensions to generate, write and clear the table under 
    its management. """

    def _init_table(self, meta, namespace, name, id_type=db.Integer):
        """ Create the given table if it does not exist, otherwise
        reflect the current table schema from the database.
        """
        name = namespace + '__' + name
        self.table = db.Table(name, meta)
        col = db.Column('id', id_type, primary_key=True)
        self.table.append_column(col)

    def _generate_table(self):
        """ Create the given table if it does not exist. """
        # TODO: make this support some kind of migration?
        if not db.engine.has_table(self.table.name):
            self.table.create(db.engine)

    def _upsert(self, bind, data, unique_columns):
        """ Upsert a set of values into the table. This will 
        query for the set of unique columns and either update an 
        existing row or create a new one. In both cases, the ID
        of the changed row will be returned. 
        """
        key = db.and_(*[self.table.c[c]==data.get(c) for \
                c in unique_columns])
        q = self.table.update(key, data)
        if bind.execute(q).rowcount == 0:
            q = self.table.insert(data)
            rs = bind.execute(q)
            return rs.inserted_primary_key[0]
        else:
            q = self.table.select(key)
            row = bind.execute(q).fetchone()
            return row['id']

    def _flush(self, bind):
        """ Delete all rows in the table. """
        q = self.table.delete()
        bind.execute(q)

    def _drop(self, bind):
        """ Drop the table and the local reference to it. """
        if db.engine.has_table(self.table.name):
            self.table.drop()
        del self.table

class DatasetFacetMixin(object):
    
    @classmethod
    def dataset_counts(cls, datasets):
        ds_ids = [d.id for d in datasets]
        q = db.select([cls.code, db.func.count(cls.dataset_id)],
            cls.dataset_id.in_(ds_ids), group_by=cls.code,
            order_by=db.func.count(cls.dataset_id).desc())
        return db.session.bind.execute(q).fetchall()

class InsertFromSelect(UpdateBase, ClauseElement):
    def __init__(self, table, select):
        self.table = table
        self.select = select

@compiler.compiles(InsertFromSelect)
def visit_insert_from_select(element, compiler, **kw):
    return "INSERT INTO %s (%s)" % (
        compiler.process(element.table, asfrom=True),
        compiler.process(element.select)
    )
