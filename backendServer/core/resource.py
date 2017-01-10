from core import threadlocal

__author__ = 'Azharul'

import sys
import datetime
import collections
import operator
import sqlalchemy
import formencode

from core.model import Model
from core.exceptions import ResourceInsertException
from core.validators import ModelValidator
from core.utils.datastructures import SortedDict
from core.page import Page


class Resource(object):
    """Used for database read/write operation

    Requires the subclasses to declare `mapper` and `validators` to be used with Resource::

        class UserResource(Resource):
            mapper = user_mapper
            validate_with = UserValidation
            validators = [UserUpdateValidation]
    """

    def __init__(self):
        self.session = threadlocal.db_session()    #: Current sqlalchemy session
        self.user = threadlocal.get_current_user() #: Currently logged in user
        if hasattr(self, 'mapper'):
            self._vindex = dict((v.__name__, v) for v in getattr(self, 'validators', ()))
            self._qindex = dict((q.__name__, q) for q in getattr(self, 'query_builders', ()))
            self._to_delete = []
            self._to_empty = []
            self._to_append = []


    @property
    def model(self):
        """Model class of the Resource.
        """
        return self.mapper.class_

    @property
    def primary_key(self):
        """Primary key column of the Model.
        """
        return self.mapper.primary_key[0].key

    @property
    def polymorphic_key(self):
        """Polymorphic identity column of the Model, `None` if Model doesn't use
        polymorphic identity.
        """
        return getattr(self.mapper.polymorphic_on, 'key', None)


    def create_validator(self, validate_with=None, **kw):
        """Creates a Validation object, using the default validator, or one of the
        validators available in the `validators` list of `Dao`.

        :param validate_with: Optional, Validation class to use

        :return: `Validation` object
        """
        return self._vindex.get(validate_with, self.validate_with)()

    def create_partial_validator(self, fields, validate_with=None, **kw):
        """Creates a new validator with the given `fields`, which are taken from
        the the default validator, or one of the validators available in the
        `validators` list of `Dao`.

        :param fields: List of fields to use in the created validator
        :param validate_with: Optional, Validation class to use

        :return: `Validation` object
        """
        validator = self._vindex.get(validate_with, self.validate_with)
        partial_validator = ModelValidator()
        for name in fields:
            if name in validator.fields:
                partial_validator.add_field(name, validator.fields[name])
        return partial_validator


    def submitted_data(self, data):
        """Returns data to be used for save/update, and the used namespace::

            data, namespace = dao.submitted_data()

        :param data: Dictionary which contains data to be saved/updated

        :return: form data, namespace
        """
        bases = [c.__name__ for c in self.model.mro() if issubclass(c, Model)]

        for namespace in bases:
            if namespace in data:
                return data[namespace], namespace

        raise KeyError("Data dictionary doesn't contain any of %s" % ', '.join(bases))

    def validate(self, data, validate_with=None, state=None, **kw):
        """Returns validated copy of `data`. `formencode.Invalid` exception raised
        in the validation process is caught and `ResourceInsertException` is raised,
        which wraps the original `formencode.Invalid` exception.

        If `validate_with` is provided then the given validator is used instead of
        default validator. The provided validator must be available in the
        `validators` list of Dao.
        """
        v = self.create_validator(validate_with, **kw)
        field_dict, namespace = self.submitted_data(data)

        try:
            return v.to_python(field_dict, state=state)
        except formencode.Invalid:
            exc_class, exc, tb = sys.exc_info()
            exc.error_dict = {namespace: exc.error_dict}
            raise ResourceInsertException((exc, self), tb)


    def create_model(self, data, validate_with=None, **kw):
        """Validates `data` and creates a new model initialized with the
        validated data. The created model is transient (not added to session)

        :param validate_with: Optional, Validation class to use

        :return: new instance of `Model`, not attached to session
        """
        cleaned_data = self.validate(data, validate_with, **kw)
        model_cls = self.mapper.polymorphic_map.get(cleaned_data.get(self.polymorphic_key), self.mapper).class_
        return self._update(self.mapper, cleaned_data, model_cls())

    def update_model(self, data, model, validate_with=None, **kw):
        """Validates `data` and updates `model` with the validated data.

        :param validate_with: Optional, Validation class to use

        :return: `model`
        """
        return self._update(self.mapper, self.validate(data, validate_with, state=model, **kw), model)

    def _update(self, mapper, data, model):
        """Updates the `mapper` mapped `model` with `data`. To create a
        new object, a transient instance should be passed as `model`. Only attributes
        mapped by `mapper` are updated with respective values from `data`.

        Limitations: Won't work with models having composite primary keys

        :param mapper: mapper object to use
        :param data: Optional, Validation class to use

        :return: `model`
        """
        for k, v in data.iteritems():
            try:
                prop = mapper.get_property(k)
            except Exception as e:
                print(e)
            if prop is None: continue

            if isinstance(prop, sqlalchemy.orm.RelationshipProperty):
                pk = prop.mapper.primary_key[0].key
                related_class = prop.mapper.class_
                # map of related objects, in {fk: fk_value} format
                if prop.direction is sqlalchemy.orm.interfaces.MANYTOMANY:
                    # flag existing models to be removed
                    self._to_empty.append(getattr(model, k))
                    # add new items
                    right_fk = prop.secondaryjoin.right.name
                    for inner_dict in v:
                        right_model = self.session.query(related_class).get(inner_dict[right_fk])
                        if right_model:
                            self._to_append.append((getattr(model, k), right_model))
                # map of related objects, in {id: data_dict} format
                elif prop.uselist:
                    related_models = dict((getattr(inner, pk), inner) for inner in getattr(model, prop.key))
                    for inner_dict in v:
                        id = inner_dict.get(pk)
                        if id:
                            self._update(prop.mapper, inner_dict, related_models[id])
                            del related_models[id]
                        else:
                            getattr(model, k).append(self._update(prop.mapper, inner_dict, related_class()))

                    # flag non-updated related models for deletion
                    self._to_delete.extend(related_models.values())
                else:
                    # TODO: Not too well tested
                    related_model = getattr(model, prop.key)
                    if related_model and v:
                        if v.get(pk):
                            self._update(prop.mapper, v, related_model)
                        else:
                            self._to_delete.append(related_model)
                    # don't create the related object if None is provided instead of a dictionary
                    elif v != None:
                        setattr(model, k, self._update(prop.mapper, v, related_class()))
                    if v == None and related_model:
                        self._to_delete.append(related_model)
            else:
                setattr(model, k, v)

        self._post_process(model)
        return model

    def _post_process(self, model):
        """Applies common changes to the model created from validated data

        Presently it sets `updated` field to current user and `updated_by` field
        to current date. If the model is newly created, then `created` and
        `created_by` field is also set to current user and current date respectively.
        """
        model.updated = datetime.datetime.today().isoformat()
        model.updated_by = self.user.id if self.user else None

        if not model._sa_instance_state.key:
            model.created = model.updated
            model.created_by = model.updated_by

    def _post_write(self, model, commit=False):
        while self._to_append:
            collection, related_model = self._to_append.pop(0)
            if related_model not in collection:
                collection.append(related_model)

        self._commit() if commit else self.session.flush()
        return model

    def create(self, data, validate_with=None, commit=False, **kw):
        """Creates a new object after validating `data` and saves it to database.

        :param validate_with: Optional, Validation class to use
        :param commit: Optional, commits the transaction if `True` is used

        :return: new instance of `Model`, saved in database, attached to the current session
        """

        model = self.create_model(data, validate_with, **kw)
        self.session.add(model)
        return self._post_write(model, commit)

    def update(self, data, models, validate_with=None, enable_delete=False, commit=False, **kw):
        """Updates a single model or a list of models from `data`.

        :param data: Data to use for update
        :param models: A single object or a list of objects
        :param validate_with: Optional, Validation class to use
        :param enable_delete: Optional, if True, then any related model absent in data is marked for deletion.
        :param commit: Optional, commits the transaction if `True` is used

        :return: A single object or a list of objects, depending on what was provided for `models` parameter
        """
        # make update work with [], () and scalar
        if isinstance(models, collections.Sequence):
            to_update = models
        else:
            to_update = [models]

        self.session.add_all([self.update_model(data, m, validate_with, **kw) for m in to_update])
        if enable_delete:
            while self._to_delete:
                self.session.delete(self._to_delete.pop(0))
            # unlink many-to-many relations
            while self._to_empty:
                collection = self._to_empty.pop(0)
                # doesn't work if we don't copy the list first
                for related_model in collection[:]:
                    collection.remove(related_model)

        # return models in its original shape
        return self._post_write(models, commit)


    def _commit(self):
        """Commits the transaction, in case of an exception performs rollback
        and re-raises the exception
        """
        try:
            self.session.commit()
        except:
            self.session.rollback()
            raise

    def group_by(self, *args, **kwargs):
        """Groups query result by variable number of keys.

        :param query: Optional, query for reading models. If not provided, all models will be read
        :param container: Optional, container class to used for groups. Uses `dict` by default

        :return: Group object, containing list property for every grouped key and `all` objects
        """
        container = kwargs.get('container', dict)
        groups = collections.namedtuple('Groups', 'all ' + ' '.join(args))((kwargs.get('query') or self.query()).all(), *[container() for _ in range(len(args))])

        for key, uselist in [(key, key != self.primary_key) for key in args]:
            group = getattr(groups, key)
            for model in groups.all:
                value = getattr(model, key)
                if uselist:
                    group.setdefault(value, []).append(model)
                else:
                    group[value] = model

        return groups

    def all(self, **kwargs):
        """Reads all objects which are mapped by the Dao's mapper. All keyword
        arguments are passed to `Dao.query`

        :return: List of objects (instances of `Model`)
        """
        return self.query(**kwargs).all()


    def query(self, *args, **kwargs):
        """Creates an SQLAlchemy query object for the model of Dao. The columns
        to read can be specified via variable number of positional arguments,
        which can be string or SQLAlchemy Column object. If string is provided
        as column, it is assumed to belong to `Dao.model`

        `own`, `branch` and `deleted` keyword arguments are reserved for access
        control.  Other keyword arguments are used in conjunction with query
        object's `filter_by` method.

        :param own: Default `False`. If `True`, filters query by Dao.model.created_by == Dao.user.id
        :param branch: Default `False`. If `True`, filters query by Dao.model.branch_id == Dao.user.branch_id
        :param deleted: Default `False`. If `True`, doesn't apply condition to exclude deleted objects
        :return: `Query` object
        """
        if len(args):
            query = self.session.query(*[getattr(self.model, f) if isinstance(f, str) else f for f in args])
        else:
            query = self.session.query(self.model)

        own = kwargs.pop('own', False)
        branch = kwargs.pop('branch', False)
        deleted = kwargs.pop('deleted', False)

        if self.user and self.user.company_id and hasattr(self.model, 'company_id'):
            query = query.filter(self.model.company_id == self.user.company_id)

        #if branch and self.user and hasattr(self.model, 'branch_id'):
        #    query = query.filter(self.model.branch_id == self.user.branch_id)
        #if hasattr(self.model, 'deleted') and deleted is not None:
        #    query = query.filter(self.model.deleted == deleted)
        if kwargs:
            query = query.filter_by(**kwargs)
        return query

    def paginate(self, query=None, page=1, limit=None, count_query=None, count=None):
        """
        :param query: sqlalchemy query object
        :param page: page no
        :param count_query: optional count query, default is None
        :param limit: number of rows in a page

        :return: Page object with page no, limit, records and rows
        """
        query = query or self.query()
        records = count if count is not None else (count_query or query).count()

        if type(limit) != int:
            limit = None

        page = Page(page, limit, records)
        offset = (page.page - 1) * page.limit
        page.rows = query.limit(page.limit).offset(offset).all()
        return page

    # Migrated from old dao
    def read(self, pk, **kwargs):
        """Reads a model from database, by primary key. Additional keyword arguments
        are passed to `Dao.query`.

        :param pk: Primary key value

        :return: Model if model is found, otherwise None
        """
        query = self.query(**kwargs).filter(getattr(self.model, self.primary_key) == pk)
        return query.first()

    # Migrated from old dao
    def findDict(self, query=None, key=None, value=None, empty_value=None, empty_text=''):
        """

        :param query: Optional, query for reading models. If not provided, all models will be read
        :param key: Optional, attribute to use as dictionary key
        :param value: Optional, attribute to use as dictionary value, if not provided uses the whole model as value

        :return: Dict of object with id as KEY and the row as VALUE
        """
        keygetter = operator.attrgetter(key or self.primary_key)
        key_property = keygetter(self.model)

        if value:
            valuegetter = {'str': str, 'unicode': str}.get(value, operator.attrgetter(value))

            try:
                value_property = valuegetter(self.model)
                if isinstance(value_property, sqlalchemy.orm.attributes.QueryableAttribute):
                    if not query and isinstance(key_property, sqlalchemy.orm.attributes.QueryableAttribute):
                        query = self.query(key_property, value_property)

                    query = query.order_by(valuegetter(self.model))
            except AttributeError:
                # Nested orm properties are not accessible with attrgetter objects
                pass

        query = query or self.query()
        result = SortedDict((keygetter(row), valuegetter(row) if value else row) for row in query.all())
        if empty_value is not None:
            result.insert(0, empty_value, empty_text)

        return result

    def option_list(self, query=None, key=None, value=None, empty_value=None, empty_text=''):
        return [dict(id=key,text=value) for key,value in self.findDict(query=query, key=key, value=value, empty_value=empty_value, empty_text=empty_text).iteritems()]