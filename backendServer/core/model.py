__author__ = 'Azharul'

import copy
import datetime
import decimal
from collections import MutableMapping
from sqlalchemy import orm, Table, Column, Integer, String, DateTime, Boolean
from django.utils.encoding import python_2_unicode_compatible
from core.page import Page
from core import threadlocal


@python_2_unicode_compatible
class Model(MutableMapping):
    """Base class of all ORM mapped objects. Supports dictionary operations.
    """
    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __delitem__(self, key):
        try:
            delattr(self, key)
        except AttributeError:
            raise KeyError

    def __iter__(self):
        return (k for k in dir(self)
                if not (k.startswith('_') or callable(getattr(self, k))))

    def __len__(self):
        return 1

    def __contains__(self, x):
        return hasattr(self, x)

    __hash__ = object.__hash__

    def __repr__(self):
        ret = '<' + str(self.__class__.__name__)

        for field, value in self.__dict__.items():
            if field[0] != '_' :
                ret += ' (' + field + ': ' + repr(value) + ')'

        ret += '>\n'
        return ret

    def __str__(self):
        return self.__repr__()

    def to_dict(self):
        return dict(self.iteritems())

    @property
    def session(self):
        """Session currently attached to the objectt
        """
        return orm.object_session(self)

    def jsonencoder(self,obj):
        """JSON encoder function for SQLAlchemy special classes."""
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, decimal.Decimal):
            return float(obj)

    @property
    def status_info(self):
        if self.deleted:
            return 'Deleted'
        elif self.inactive:
            return 'Inactive'
        else:
            return 'Active'


class QueryProperty(object):
    """Base class of Generic Relationship properties. Implements SQLAlchemy's Query like interface
    for querying objects related via Generic Relationship.
    """
    def query(self):
        raise NotImplementedError

    def __iter__(self):
        return iter(self.query())

    def __getitem__(self, item):
        return self.query().__getitem__(item)

    @property
    def session(self):
        return threadlocal.db_session()

    def filter(self, *args):
        return self.query().filter(*args)

    def get(self, id):
        return self.query().filter(self.related_class.id == id).first()

    def all(self):
        return self.query().all()

    def first(self):
        return self.query().first()

    def last(self):
        return self.query().order_by(self.related_class.id.desc()).limit(1).first()

    def count(self):
        return self.query().count()

    def paginate(self, query=None, page=1, limit=10):
        query = query or self.query()
        page = Page(page, limit, query.count())
        offset = (page.page - 1) * page.limit
        page.rows = query.limit(page.limit).offset(offset).all()
        return page


class ListProperty(QueryProperty):
    """Collection Property for accessing subset of Generic Relation objcts,
    separated by value of `type` column in the related object. Default value of
    the collection is marked by `default` flag in the related object.
    """
    def __init__(self, polymorphic_identity):
        self.type = polymorphic_identity

    def __get__(self, instance, owner):
        self.relation = instance
        self.related_class = instance.related_class
        if not hasattr(self.related_class, 'type'):
            raise TypeError("%s doesn't have 'type' property" % repr(self.related_class))

        return self

    def query(self):
        """Query for getting the objects in collection
        """
        return self.relation.query().filter(self.related_class.type == self.type)

    @property
    def default(self):
        """Default object among the collection
        """
        if not hasattr(self.related_class, 'default'):
            raise TypeError("%s doesn't have 'default' property" % repr(self.related_class))

        return self.query().filter(self.related_class.default == True).first()


class GenericRelation(QueryProperty):
    """Property for associating any type of object with another type of object
    without changing schema. The related class must have `table_name` and `table_key`
    column to support Generic Relationship.
    """
    def __init__(self, related_class):
        """
        :param related_class:
        """
        self.related_class = related_class
        self._type_map = dict([(getattr(self, attr).type, attr) for attr in dir(self)
                               if isinstance(getattr(self, attr), QueryProperty) and hasattr(getattr(self, attr), 'type')])

    def __get__(self, instance, owner):
        if instance is None:
            return self

        clone = copy.deepcopy(self)
        clone.table_name = orm.object_mapper(instance).base_mapper.mapped_table.name
        clone.model = instance
        return clone

    def query(self):
        """Query for getting the related objects
        """
        return self.session.query(self.related_class) \
                .filter(self.related_class.table_name == self.table_name) \
                .filter(self.related_class.table_key == self.model.id)

    def get_property(self, polymorphic_identity):
        """Returns ListProperty for accessing a subset of the related objects,
        differntiated by value of the `type` column in the related object.

        :param polymorphic_identity: Value of the `type` column

        :return: ListProperty for accsesing the objects having `polymorphic_idenitity` as `type` value.
        """
        return getattr(self, self._type_map[polymorphic_identity])