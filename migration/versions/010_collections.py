from sqlalchemy import *
from migrate import *

meta = MetaData()

def upgrade(migrate_engine):
    meta.bind = migrate_engine
    dataset = Table('dataset', meta, autoload=True)

    for dataset_name, in meta.bind.execute(select([dataset.name])):
        entry_collection_table = Table('%s__entry_collection' % dataset_name, meta,
                                       Column('id', Integer, primary_key=True),
                                       Column('name', Unicode(255), unique=True),
                                       Column('label', Unicode(2000)),
                                       Column('description', Unicode),
                                       Column('created_at', DateTime),
                                       Column('updated_at', DateTime),
                                       )
        entry_collection_table.create()

        entry_collection_entry_table = Table('%s__entry_collection' % dataset_name, meta,
                                       Column('entry_id', Unicode(42), primary_key=True),
                                       Column('collection_id', Integer, primary_key=True),
                                       )
        entry_collection_entry_table.create()
