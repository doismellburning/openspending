import colander

from openspending.model import meta as db
from datetime import datetime
from openspending.model.common import TableHandler

class BaseEntryCollection(object):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(255), unique=True)
    label = db.Column(db.Unicode(2000))
    description = db.Column(db.Unicode())
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    @classmethod
    def by_id(cls, id):
        return db.session.query(cls).filter_by(id=id).first()

    @classmethod
    def by_name(cls, name):
        return db.session.query(cls).filter_by(name=name).first()

    @classmethod
    def all(cls):
        return db.session.query(cls).all()

    def add_entry(self, entry_id):
        if self.find_entry(entry_id) is not None:
            return None
        x = self.entry_collection_entry(self, entry_id)
        db.session.add(x)
        return x

    def find_entry(self, entry_id):
        return db.session.query(self.entry_collection_entry).\
               filter(self.entry_collection_entry.collection_id == self.id).\
               filter(self.entry_collection_entry.entry_id == entry_id).\
               first()

    def remove_from_collection(self, entry_id):
        x = self.find_entry(entry_id)
        db.session.delete(x)

    def __init__(self, name):
        assert name != ''
        self.name = name
        self.label = name

    def __str__(self):
        return "<EntryCollection(%s, %s)>" % (self.dataset_name, self.name)

    def __repr__(self):
        return "<EntryCollection(%s, %s)>" % (self.dataset_name, self.id)

class BaseEntryCollectionEntry(object):
    @db.declared_attr
    def entry_id(cls):
        return db.Column(cls.entry_table.c.id.type, db.ForeignKey(entry_table.c.id), primary_key=True)

    @db.declared_attr
    def collection_id(cls):
        return db.Column(cls.entry_collection_class.id.type, db.ForeignKey(cls.entry_collection_class.id), primary_key=True)

    # TODO: map the entry table to a class and use that
    #@db.declared_attr
    #def entry(cls):
    #    return db.relationship(cls.entry_table, backref='collections')

    @db.declared_attr
    def collection(cls):
        return db.relationship(cls.entry_collection_class, backref='entries', cascade='all')

    def __init__(self, collection, id):
        self.collection_id = collection.id
        self.entry_id = id

    def __str__(self):
        return "<EntryCollectionEntry(%s, %s)>" % (self.dataset_name, self.collection.name, self.entry_id)

    def __repr__(self):
        return "<EntryCollectionEntry(%s, %s, %s)>" % (self.dataset_name, self.collection_id, self.entry_id)

def make_entry_collection_class(dataset_name, declarative):
    fields = {'__tablename__': dataset_name + '__entry_collection',
              'dataset_name': dataset_name,
              }

    classname = 'EntryCollection_' + dataset_name
    
    return type(classname.encode('utf-8'), (BaseEntryCollection, declarative), fields)

def make_entry_collection_entry_class(dataset_name, declarative, entry_collection_class, entry_table):
    fields = {'__tablename__': dataset_name + '__entry_collection_entry',
              'entry_table': entry_table,
              'entry_collection_class': entry_collection_class,
              'dataset_name': dataset_name,
              'entry_id': db.Column(entry_table.c.id.type, db.ForeignKey(entry_table.c.id), primary_key=True),
              'collection_id': db.Column(db.Integer, db.ForeignKey(entry_collection_class.id), primary_key=True),
              }

    classname = 'EntryCollectionEntry_' + dataset_name

    cls = type(classname.encode('utf-8'), (BaseEntryCollectionEntry, declarative), fields)
    entry_collection_class.entry_collection_entry = cls
    return cls

def make_entry_collection_classes(dataset_name, declarative, entry_table):
    entry_collection_class = make_entry_collection_class(dataset_name, declarative)
    entry_collection_entries_class = make_entry_collection_entry_class(dataset_name, declarative, entry_collection_class, entry_table)
    return entry_collection_class, entry_collection_entries_class

class EntryCollectionCreate(colander.MappingSchema):
    name = colander.SchemaNode(colander.String(),
                               validator=colander.Regex(r"^[a-zA-Z0-9_\-]{3,255}$"))

    label = colander.SchemaNode(colander.String())
    description = colander.SchemaNode(colander.String(), missing=None, default=None)


class EntryCollectionUpdate(colander.MappingSchema):
    label = colander.SchemaNode(colander.String())
    description = colander.SchemaNode(colander.String(), missing=None, default=None)
