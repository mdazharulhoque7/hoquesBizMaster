from core import threadlocal

__author__ = 'Azharul'

import datetime
import decimal
import hashlib
import json
import formencode
from sqlalchemy.sql import select
from formencode import validators, Invalid, Schema, declarative
from core.utils.datastructures import EnumValue


class Number(validators.RangeValidator):
    messages = {
        'tooLow': "Please enter a number that is %(min)s or greater",
        'tooHigh':"Please enter a number that is %(max)s or smaller",
        'decimal': "Please enter a decimal amount",
    }
    """
    Convert a value to Decimal

    Example::
        >>> Decimal.to_python('10')
        10
        >>> Decimal.to_python('10.5')
        10.5
        >>> Decimal.to_python('ten')
        Traceback (most recent call last):
            ...
        Invalid: Please enter a decimal value
        >>> Decimal(min=5).to_python('6.5')
        6.5
        >>> Decimal(max=10.5).to_python('11.5')
        Traceback (most recent call last):
            ...
        Invalid: Please enter a number that is 10.5 or smaller
    """
    max = 10000000000000000000000000
    messages = { 'decimal': "Please enter a number" }

    def _to_python(self, value, state):
        try:
            return decimal.Decimal(value)
        except (TypeError, decimal.InvalidOperation):
            raise Invalid(self.message('decimal', state), value, state)


class UNumber(Number):
    min = decimal.Decimal(0)

class PNumber(Number):
    min = decimal.Decimal(1)

class YNumber(Number):
    min = decimal.Decimal(0)
    max = decimal.Decimal(365)

class UInt(validators.Int):
    min = 0

class PInt(validators.Int):
    min = 1


class Constant(validators.Constant):
    """
    Like validators.Constant, but the default value is also used for `if_missing` case
    """
    def __initargs__(self, new_attrs):
        setattr(self, 'if_missing', self.value)


class BaseDateTimeValidator(validators.RangeValidator):
    """Base class for Date/DateTime validator. Adds support for `auto_now`
    """
    auto_now = False
    now = None
    format = None
    object_type = None

    messages = {
        'invalid': "Please enter a valid %s",
        'tooLow': "Please enter a %s that is %(min)s or greater",
        'tooHigh': "Please enter a %s that is %(max)s or smaller"
    }

    def __initargs__(self, new_attrs):
        self.type_name = self.object_type.__class__.__name__

        if self.auto_now:
            self.if_empty = self.now
            self.if_missing = self.now

    def _to_python(self, value, state):
        if isinstance(value, self.object_type):
            return value

        try:
            return datetime.datetime.strptime(value, self.format)
        except (TypeError, ValueError):
            raise Invalid(self.message('invalid', state), value, state)


class Date(BaseDateTimeValidator):
    format = '%Y-%m-%d'
    object_type = datetime.date
    now = datetime.date.today

    messages = {
        'invalid': "Please enter a valid date",
        'tooLow': "Please enter a date that is %(min)s or greater",
        'tooHigh': "Please enter a date that is %(max)s or smaller"
    }

    def _to_python(self, value, state):
        value = super(Date, self)._to_python(value, state)
        if isinstance(value, datetime.datetime):
            return value.date()

        return value


class DateTime(BaseDateTimeValidator):
    format =  '%Y-%m-%d %H:%M'
    object_type = datetime.datetime
    now = datetime.datetime.now

    messages = {
        'invalid': "Please enter a valid datetime",
        'tooLow': "Please enter a datetime that is %(min)s or greater",
        'tooHigh': "Please enter a datetime that is %(max)s or smaller"
    }


class TimeValidator(BaseDateTimeValidator):
    format =  '%H:%M:%S'
    object_type = datetime.time
    now = lambda: datetime.datetime.now().time()

    messages = {
        'invalid': "Please enter a valid time",
        'tooLow': "Please enter a time that is %(min)s or greater",
        'tooHigh': "Please enter a time that is %(max)s or smaller"
    }

    def _to_python(self, value, state):
        try:
            value = datetime.datetime.strptime(value, '%H:%M:%S')
        except (TypeError, ValueError):
            try:
                value = datetime.datetime.strptime(value, '%H:%M')
            except (TypeError, ValueError):
                raise Invalid(self.message('invalid', state), value, state)

        if isinstance(value, datetime.datetime):
            return value.time()

        return value


class FieldMax(validators.FormValidator):
    field_name = None
    __unpackargs__ = ('field_name', 'max')

    messages = {
        'invalid': "Upto %(max)s allowed",
    }

    def validate_python(self, field_dict, state):
        value, max_value  = field_dict[self.field_name], field_dict[self.max]
        if (value and max_value) is not None and value > max_value:
            message = self.message('invalid', state, max=max_value)
            raise Invalid(message, field_dict, state,
                          error_dict={self.field_name: message})


class FieldMin(validators.FormValidator):
    field_name = None
    __unpackargs__ = ('field_name', 'min')

    messages = {
        'invalid': "Minimum %(min)s required",
    }

    def validate_python(self, field_dict, state):
        value, min_value  = field_dict[self.field_name], field_dict[self.min]
        if (value and min_value) is not None and value < min_value:
            message = self.message('invalid', state, min=min_value)
            raise Invalid(message, field_dict, state,
                          error_dict={self.field_name: message})


class FieldNotEqual(validators.FormValidator):
    field_name = None
    __unpackargs__ = ('field_name', 'compare_with')

    messages = {
        'invalid': "Select a different value",
    }

    def validate_python(self, field_dict, state):
        if field_dict[self.field_name] == field_dict[self.compare_with]:
            message = self.message('invalid', state, compare_with=field_dict[self.compare_with])
            raise Invalid(message, field_dict, state,
                          error_dict={self.field_name: message})


class IPRange(validators.FancyValidator):
    """
    Checks a valid IP address or IP Address range (e.g. 192.168.0.1, 192.168.0.*)
    """
    messages = {
        'invalid_ip': "Not a valid IP Address or IP Address Range"
    }

    def _to_python(self, value, state):
        parts = value.split('.')
        if len(parts) != 4:
            raise Invalid(self.message('invalid_ip', state), value, state)

        parts = [p for p in parts if (p.isdigit() and 0 <= int(p) <= 255) or p == '*']
        if len(parts) != 4:
            raise Invalid(self.message('invalid_ip', state), value, state)

        return '.'.join(parts)

class FileDate(validators.RangeValidator):
    formats = ["%m/%d/%Y", "%m.%d.%Y", "%Y-%m-%d"]
    object_type = datetime.date
    now = datetime.date.today

    messages = {
        'invalid': "Please enter a valid date",
        'tooLow': "Please enter a date that is %(min)s or greater",
        'tooHigh': "Please enter a date that is %(max)s or smaller"
    }
    def _to_python(self, value, state):
        if isinstance(value, self.object_type):
            return value
        try:
            return datetime.datetime.strptime(value, self.formats[0])
        except (TypeError, ValueError):
            try:
                return datetime.datetime.strptime(value, self.formats[1])
            except (TypeError, ValueError):
                try:
                    return datetime.datetime.strptime(value, self.formats[2])
                except (TypeError, ValueError):
                    raise Invalid(self.message('invalid', state), value, state)

class HashedPassword(validators.FancyValidator):
    """
    Returns sha1 hash of value
    """
    def _to_python(self, value, state):
        return hashlib.sha512(value).hexdigest()


class FormatValidator(validators.Regex):
    """
    Validates printf format strings (allows only one %d or %.[1-6]f)
    """
    strip = True
    regex = r'^[^%]*%(?:d|\.[1-6]f)\b[^%]*$'

    messages = {'invalid': "Please select a valid printf format (%%d or %%.[1-6]f)"}


class SimpleEnumValidator(validators.Int):
    """Checks an integer value's membership in a SimpleEnum

    Both EnumValue and int can be used for defaults like if_empty, if_missing

    Usage:
        >>> SimpleEnumValidator(E_VoucherStatus).to_python(E_VoucherStatus.Pending)
        0
        >>> SimpleEnumValidator(E_VoucherStatus).to_python(2)
        2
    """
    messages = {
        'invalid': "Please select a valid option"
    }
    enum = None
    __unpackargs__ = ('enum',)

    def __initargs__(self, new_attrs):
        for attr, value in ((k, new_attrs.get(k)) for k in ('default', 'if_empty', 'if_missing', 'if_invalid')):
            if isinstance(value, EnumValue):
                setattr(self, attr, value.index)

    def _to_python(self, value, state):
        if isinstance(value, EnumValue):
            return value.index

        return super(SimpleEnumValidator, self)._to_python(value, state)

    def validate_python(self, value ,state):
        if value not in self.enum:
            raise Invalid(self.message('invalid', state), value, state)


class JSONField(validators.FancyValidator):
    def _to_python(self, value, state):
        return json.dumps(value)


class ForeignKey(validators.Int):
    """Takes a database column to check converted value's existence

    >>> ForeignKey(parties_table.c.id).to_python('10')
    10
    """
    column = None
    __unpackargs__ = ('column',)

    def validate_python(self, value, state):
        if value is None or not hasattr(state, 'session'): return

        query = select([self.column], self.column == value)
        if not state.session.execute(query).rowcount:
            raise Invalid("%d doesn't exist" % value, state)


class AnyFilled(validators.FormValidator):
    __unpackargs__ = ('*', 'fields')
    func = None

    def validate_python(self, field_dict, state):
        if not any(filter(self.func, [field_dict[key] for key in self.fields])):
            raise Invalid("Any of %s is required" % ', '.join(self.fields),
                          field_dict, state, error_dict={})


class AllFilled(validators.FormValidator):
    __unpackargs__ = ('*', 'fields')
    func = None

    def validate_python(self, field_dict, state):
        if not filter(self.func, [field_dict[key] for key in self.fields]):
            error_dict = dict([(key, "Please select a value") for key in self.fields])
            raise Invalid("All of %s is required" % ', '.join(self.fields),
                          field_dict, state, error_dict=error_dict)



class PreserveState(validators.FormValidator):
    """Updates the field_dict with state values when state is available
    """
    __unpackargs__ = ('*', 'fields')

    def _to_python(self, field_dict, state):
        if state:
            for field in self.fields:
                if hasattr(state, field):
                    field_dict[field] = getattr(state, field)

        return field_dict


class Set(validators.Set):
    if_empty = validators.NoDefault
    if_missing = validators.NoDefault



#def HashedPassword(form, field):
#    field.data = hash_password(field.data)
#    return field

# ------------------------------------------------------------------------------------------------------------------------------------------------------
#                            SQL Alchemy Model Validator Class
#-------------------------------------------------------------------------------------------------------------------------------------------------------

class ExtendedInherit(formencode.declarative.DeclarativeMeta):
    """Adds support for extending pre_validators/chained_validators, and
    `allowed_fields` property for restricting validation to a subset of fields.

    Like DeclarativeMeta, it doesn't support multiple inheritance.
    Use SchemaMixin where you would use multiple inheritance.
    """
    def __new__(meta, name, bases, props):
        # Extends pre_validators/chained_validators depending on value of
        # `extend_pre_validators` and `extend_chained_validators` respectively
        for to_extend in ('pre_validators', 'chained_validators',):
            if props.get('extend_' + to_extend, True):
                props[to_extend] = getattr(bases[0], to_extend, []) + props.get(to_extend, [])

        return formencode.declarative.DeclarativeMeta.__new__(meta, name, bases, props)

    def __init__(cls, name, bases, attrs):
        # Restricts validation to `allowed_fields` if `allowed_fields was declared
        if getattr(cls, 'allowed_fields', False):
            for k in cls.fields.keys():
                if k not in cls.allowed_fields:
                    del cls.fields[k]

            del cls.allowed_fields


class ModelValidator(Schema):
    """Adds support for callable default/min/max values, 'allowed_fields',
    'ignored_fields', extending pre_validators/chained_validtors, callable
    default values, and `default` property in field objects for specifying
    if_empty/if_missing at once.
    """
    __metaclass__ = ExtendedInherit

    allow_extra_fields = True
    filter_extra_fields = True
    extend_pre_validators = True
    extend_chained_validators = True

    pre_validators = [PreserveState('inactive') ]

    def __init__(self, *args, **kwargs):
        Schema.__init__(self, *args, **kwargs)

        for v in self.fields.itervalues():
            for attr in ('if_empty', 'if_missing', 'if_invalid', 'min', 'max', 'value'):
                if hasattr(v, attr):
                    default = getattr(v, attr)
                    if default is not formencode.api.NoDefault and callable(default):
                        setattr(v, attr, default())

    @declarative.classinstancemethod
    def add_field(self, cls, name, validator):
        """Adds support for 'default' attribute in fields.

        Sets `if_empty` and `if_missing` to `default` when `default` is declared,
        but `if_empty`, `if_missing` is not specified
        """
        if hasattr(validator, 'default'):
            for attr in ('if_empty', 'if_missing'):
                if getattr(validator, attr) is formencode.NoDefault:
                    setattr(validator, attr, validator.default)

        Schema.add_field.func(self, cls, name, validator)

    def _to_python(self, value_dict, state):
        return Schema._to_python(self, value_dict, getattr(self, 'dao', state))

    @classmethod
    def default_data(cls, model_name):
        """Supply default data for forms
        """
        def default_value(field):
            if field.if_empty is formencode.api.NoDefault:
                return ''

            return field.if_empty() if callable(field.if_empty) else field.if_empty

        defaults = dict((k, default_value(f)) for k, f in cls.fields.iteritems())
        return {model_name: defaults}

    @property
    def current_user(self):
        return threadlocal.get_current_user()

    inactive = validators.StringBool(default=False)
    deleted = Constant(False, visible=False)