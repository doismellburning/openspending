from StringIO import StringIO
import csv
import unittest

from nose.tools import assert_raises

from openspending.test.unit.model.helpers import \
        SIMPLE_MODEL, TEST_DATA
from openspending.test import DatabaseTestCase, helpers as h

from openspending.model import meta as db
from openspending.model import Dataset

class TestComplexDimension(DatabaseTestCase):

    def setup(self):
        self.engine = db.engine 
        self.meta = db.metadata #MetaData()
        self.meta.bind = self.engine
        self.ds = Dataset(SIMPLE_MODEL)
        self.reader = csv.DictReader(StringIO(TEST_DATA))
        self.entity = self.ds['to']
        self.classifier = self.ds['function']

    def test_basic_properties(self):
        self.ds.generate()
        assert self.entity.name=='to', self.entity.name
        assert self.classifier.name=='function', self.classifier.name
        assert self.entity.scheme=='entity', self.entity.scheme
        assert self.classifier.scheme=='funny', self.classifier.scheme
        
    def test_generated_tables(self):
        assert not hasattr(self.entity, 'table'), self.entity
        self.ds.generate()
        assert hasattr(self.entity, 'table'), self.entity
        assert self.entity.table.name=='test_' + self.entity.scheme, self.entity.table.name
        assert hasattr(self.entity, 'alias')
        assert self.entity.alias.name==self.entity.name, self.entity.alias.name
        cols = self.entity.table.c
        assert 'id' in cols
        assert_raises(KeyError, cols.__getitem__, 'field')

    def test_attributes_exist_on_object(self):
        assert len(self.entity.attributes)==3, self.entity.attributes
        assert_raises(KeyError, self.entity.__getitem__, 'field')
        assert self.entity['name'].name=='name'
        assert self.entity['name'].datatype=='string'
        assert self.entity['const'].default=='true'

    def test_attributes_exist_on_table(self):
        self.ds.generate()
        assert hasattr(self.entity, 'table'), self.entity
        assert 'name' in self.entity.table.c, self.entity.table.c
        assert 'label' in self.entity.table.c, self.entity.table.c
