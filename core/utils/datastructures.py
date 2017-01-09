__author__ = 'Azharul'

import six
import re
import copy
import collections
from collections import OrderedDict


class MergeDict(object):
    """
    A simple class for creating new "virtual" dictionaries that actually look
    up values in more than one dictionary, passed in the constructor.

    If a key appears in more than one of the given dictionaries, only the
    first occurrence will be used.
    """
    def __init__(self, *dicts):
        self.dicts = dicts

    def __bool__(self):
        return any(self.dicts)

    def __nonzero__(self):
        return type(self).__bool__(self)

    def __getitem__(self, key):
        for dict_ in self.dicts:
            try:
                return dict_[key]
            except KeyError:
                pass
        raise KeyError(key)

    def __copy__(self):
        return self.__class__(*self.dicts)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    # This is used by MergeDicts of MultiValueDicts.
    def getlist(self, key):
        for dict_ in self.dicts:
            if key in dict_:
                return dict_.getlist(key)
        return []

    def _iteritems(self):
        seen = set()
        for dict_ in self.dicts:
            for item in six.iteritems(dict_):
                k = item[0]
                if k in seen:
                    continue
                seen.add(k)
                yield item

    def _iterkeys(self):
        for k, v in self._iteritems():
            yield k

    def _itervalues(self):
        for k, v in self._iteritems():
            yield v

    if six.PY3:
        items = _iteritems
        keys = _iterkeys
        values = _itervalues
    else:
        iteritems = _iteritems
        iterkeys = _iterkeys
        itervalues = _itervalues

        def items(self):
            return list(self.iteritems())

        def keys(self):
            return list(self.iterkeys())

        def values(self):
            return list(self.itervalues())

    def has_key(self, key):
        for dict_ in self.dicts:
            if key in dict_:
                return True
        return False

    __contains__ = has_key

    __iter__ = _iterkeys

    def copy(self):
        """Returns a copy of this object."""
        return self.__copy__()

    def __str__(self):
        '''
        Returns something like

            "{'key1': 'val1', 'key2': 'val2', 'key3': 'val3'}"

        instead of the generic "<object meta-data>" inherited from object.
        '''
        return str(dict(self.items()))

    def __repr__(self):
        '''
        Returns something like

            MergeDict({'key1': 'val1', 'key2': 'val2'}, {'key3': 'val3'})

        instead of generic "<object meta-data>" inherited from object.
        '''
        dictreprs = ', '.join(repr(d) for d in self.dicts)
        return '%s(%s)' % (self.__class__.__name__, dictreprs)


class SortedDict(dict):
    """
    A dictionary that keeps its keys in the order in which they're inserted.
    """
    def __new__(cls, *args, **kwargs):
        instance = super(SortedDict, cls).__new__(cls, *args, **kwargs)
        instance.keyOrder = []
        return instance

    def __init__(self, data=None):
        if data is None or isinstance(data, dict):
            data = data or []
            super(SortedDict, self).__init__(data)
            self.keyOrder = list(data) if data else []
        else:
            super(SortedDict, self).__init__()
            super_set = super(SortedDict, self).__setitem__
            for key, value in data:
                # Take the ordering from first key
                if key not in self:
                    self.keyOrder.append(key)
                # But override with last value in data (dict() does this)
                super_set(key, value)

    def __deepcopy__(self, memo):
        return self.__class__([(key, copy.deepcopy(value, memo))
                               for key, value in self.items()])

    def __copy__(self):
        # The Python's default copy implementation will alter the state
        # of self. The reason for this seems complex but is likely related to
        # subclassing dict.
        return self.copy()

    def __setitem__(self, key, value):
        if key not in self:
            self.keyOrder.append(key)
        super(SortedDict, self).__setitem__(key, value)

    def __delitem__(self, key):
        super(SortedDict, self).__delitem__(key)
        self.keyOrder.remove(key)

    def __iter__(self):
        return iter(self.keyOrder)

    def __reversed__(self):
        return reversed(self.keyOrder)

    def pop(self, k, *args):
        result = super(SortedDict, self).pop(k, *args)
        try:
            self.keyOrder.remove(k)
        except ValueError:
            # Key wasn't in the dictionary in the first place. No problem.
            pass
        return result

    def popitem(self):
        result = super(SortedDict, self).popitem()
        self.keyOrder.remove(result[0])
        return result

    def _iteritems(self):
        for key in self.keyOrder:
            yield key, self[key]

    def _iterkeys(self):
        for key in self.keyOrder:
            yield key

    def _itervalues(self):
        for key in self.keyOrder:
            yield self[key]

    if six.PY3:
        items = _iteritems
        keys = _iterkeys
        values = _itervalues
    else:
        iteritems = _iteritems
        iterkeys = _iterkeys
        itervalues = _itervalues

        def items(self):
            return [(k, self[k]) for k in self.keyOrder]

        def keys(self):
            return self.keyOrder[:]

        def values(self):
            return [self[k] for k in self.keyOrder]

    def update(self, dict_):
        for k, v in six.iteritems(dict_):
            self[k] = v

    def setdefault(self, key, default):
        if key not in self:
            self.keyOrder.append(key)
        return super(SortedDict, self).setdefault(key, default)

    def insert(self, index, key, value):
        """Inserts the key, value pair before the item with the given index."""
        if key in self.keyOrder:
            n = self.keyOrder.index(key)
            del self.keyOrder[n]
            if n < index:
                index -= 1
        self.keyOrder.insert(index, key)
        super(SortedDict, self).__setitem__(key, value)

    def copy(self):
        """Returns a copy of this object."""
        # This way of initializing the copy means it works for subclasses, too.
        return self.__class__(self)

    def __repr__(self):
        """
        Replaces the normal dict.__repr__ with a version that returns the keys
        in their sorted order.
        """
        return '{%s}' % ', '.join('%r: %r' % (k, v) for k, v in six.iteritems(self))

    def clear(self):
        super(SortedDict, self).clear()
        self.keyOrder = []


class OrderedSet(object):
    """
    A set which keeps the ordering of the inserted items.
    Currently backs onto OrderedDict.
    """

    def __init__(self, iterable=None):
        self.dict = OrderedDict(((x, None) for x in iterable) if iterable else [])

    def add(self, item):
        self.dict[item] = None

    def remove(self, item):
        del self.dict[item]

    def discard(self, item):
        try:
            self.remove(item)
        except KeyError:
            pass

    def __iter__(self):
        return iter(self.dict.keys())

    def __contains__(self, item):
        return item in self.dict

    def __nonzero__(self):
        return bool(self.dict)


class MultiValueDictKeyError(KeyError):
    pass


class MultiValueDict(dict):
    """
    A subclass of dictionary customized to handle multiple values for the
    same key.

    >>> d = MultiValueDict({'name': ['Adrian', 'Simon'], 'position': ['Developer']})
    >>> d['name']
    'Simon'
    >>> d.getlist('name')
    ['Adrian', 'Simon']
    >>> d.getlist('doesnotexist')
    []
    >>> d.getlist('doesnotexist', ['Adrian', 'Simon'])
    ['Adrian', 'Simon']
    >>> d.get('lastname', 'nonexistent')
    'nonexistent'
    >>> d.setlist('lastname', ['Holovaty', 'Willison'])

    This class exists to solve the irritating problem raised by cgi.parse_qs,
    which returns a list for every key, even though most Web forms submit
    single name-value pairs.
    """
    def __init__(self, key_to_list_mapping=()):
        super(MultiValueDict, self).__init__(key_to_list_mapping)

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__,
                             super(MultiValueDict, self).__repr__())

    def __getitem__(self, key):
        """
        Returns the last data value for this key, or [] if it's an empty list;
        raises KeyError if not found.
        """
        try:
            list_ = super(MultiValueDict, self).__getitem__(key)
        except KeyError:
            raise MultiValueDictKeyError(repr(key))
        try:
            return list_[-1]
        except IndexError:
            return []

    def __setitem__(self, key, value):
        super(MultiValueDict, self).__setitem__(key, [value])

    def __copy__(self):
        return self.__class__([
            (k, v[:])
            for k, v in self.lists()
        ])

    def __deepcopy__(self, memo=None):
        if memo is None:
            memo = {}
        result = self.__class__()
        memo[id(self)] = result
        for key, value in dict.items(self):
            dict.__setitem__(result, copy.deepcopy(key, memo),
                             copy.deepcopy(value, memo))
        return result

    def __getstate__(self):
        obj_dict = self.__dict__.copy()
        obj_dict['_data'] = dict((k, self.getlist(k)) for k in self)
        return obj_dict

    def __setstate__(self, obj_dict):
        data = obj_dict.pop('_data', {})
        for k, v in data.items():
            self.setlist(k, v)
        self.__dict__.update(obj_dict)

    def get(self, key, default=None):
        """
        Returns the last data value for the passed key. If key doesn't exist
        or value is an empty list, then default is returned.
        """
        try:
            val = self[key]
        except KeyError:
            return default
        if val == []:
            return default
        return val

    def getlist(self, key, default=None):
        """
        Returns the list of values for the passed key. If key doesn't exist,
        then a default value is returned.
        """
        try:
            return super(MultiValueDict, self).__getitem__(key)
        except KeyError:
            if default is None:
                return []
            return default

    def setlist(self, key, list_):
        super(MultiValueDict, self).__setitem__(key, list_)

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
            # Do not return default here because __setitem__() may store
            # another value -- QueryDict.__setitem__() does. Look it up.
        return self[key]

    def setlistdefault(self, key, default_list=None):
        if key not in self:
            if default_list is None:
                default_list = []
            self.setlist(key, default_list)
            # Do not return default_list here because setlist() may store
            # another value -- QueryDict.setlist() does. Look it up.
        return self.getlist(key)

    def appendlist(self, key, value):
        """Appends an item to the internal list associated with key."""
        self.setlistdefault(key).append(value)

    def _iteritems(self):
        """
        Yields (key, value) pairs, where value is the last item in the list
        associated with the key.
        """
        for key in self:
            yield key, self[key]

    def _iterlists(self):
        """Yields (key, list) pairs."""
        return six.iteritems(super(MultiValueDict, self))

    def _itervalues(self):
        """Yield the last value on every key list."""
        for key in self:
            yield self[key]

    if six.PY3:
        items = _iteritems
        lists = _iterlists
        values = _itervalues
    else:
        iteritems = _iteritems
        iterlists = _iterlists
        itervalues = _itervalues

        def items(self):
            return list(self.iteritems())

        def lists(self):
            return list(self.iterlists())

        def values(self):
            return list(self.itervalues())

    def copy(self):
        """Returns a shallow copy of this object."""
        return copy.copy(self)

    def update(self, *args, **kwargs):
        """
        update() extends rather than replaces existing key lists.
        Also accepts keyword args.
        """
        if len(args) > 1:
            raise TypeError("update expected at most 1 arguments, got %d" % len(args))
        if args:
            other_dict = args[0]
            if isinstance(other_dict, MultiValueDict):
                for key, value_list in other_dict.lists():
                    self.setlistdefault(key).extend(value_list)
            else:
                try:
                    for key, value in other_dict.items():
                        self.setlistdefault(key).append(value)
                except TypeError:
                    raise ValueError("MultiValueDict.update() takes either a MultiValueDict or dictionary")
        for key, value in six.iteritems(kwargs):
            self.setlistdefault(key).append(value)

    def dict(self):
        """
        Returns current object as a dict with singular values.
        """
        return dict((key, self[key]) for key in self)


class ImmutableList(tuple):
    """
    A tuple-like object that raises useful errors when it is asked to mutate.

    Example::

        >>> a = ImmutableList(range(5), warning="You cannot mutate this.")
        >>> a[3] = '4'
        Traceback (most recent call last):
            ...
        AttributeError: You cannot mutate this.
    """

    def __new__(cls, *args, **kwargs):
        if 'warning' in kwargs:
            warning = kwargs['warning']
            del kwargs['warning']
        else:
            warning = 'ImmutableList object is immutable.'
        self = tuple.__new__(cls, *args, **kwargs)
        self.warning = warning
        return self

    def complain(self, *wargs, **kwargs):
        if isinstance(self.warning, Exception):
            raise self.warning
        else:
            raise AttributeError(self.warning)

    # All list mutation functions complain.
    __delitem__ = complain
    __delslice__ = complain
    __iadd__ = complain
    __imul__ = complain
    __setitem__ = complain
    __setslice__ = complain
    append = complain
    extend = complain
    insert = complain
    pop = complain
    remove = complain
    sort = complain
    reverse = complain


class DictWrapper(dict):
    """
    Wraps accesses to a dictionary so that certain values (those starting with
    the specified prefix) are passed through a function before being returned.
    The prefix is removed before looking up the real value.

    Used by the SQL construction code to ensure that values are correctly
    quoted before being used.
    """
    def __init__(self, data, func, prefix):
        super(DictWrapper, self).__init__(data)
        self.func = func
        self.prefix = prefix

    def __getitem__(self, key):
        """
        Retrieves the real value after stripping the prefix string (if
        present). If the prefix is present, pass the value through self.func
        before returning, otherwise return the raw value.
        """
        if key.startswith(self.prefix):
            use_func = True
            key = key[len(self.prefix):]
        else:
            use_func = False
        value = super(DictWrapper, self).__getitem__(key)
        if use_func:
            return self.func(value)
        return value



class EnumException(Exception):
    """ Base class for all exceptions in this module """
    def __init__(self):
        if self.__class__ is EnumException:
            raise NotImplementedError("%s is an abstract class for subclassing" % self.__class__)

class EnumEmptyError(AssertionError, EnumException):
    """ Raised when attempting to create an empty enumeration """

    def __str__(self):
        return "Enumerations cannot be empty"

class EnumBadKeyError(TypeError, EnumException):
    """ Raised when creating an Enum with non-string keys """

    def __init__(self, key):
        self.key = key

    def __str__(self):
        return "Enumeration keys must be strings: %s" % (self.key,)

class EnumImmutableError(TypeError, EnumException):
    """ Raised when attempting to modify an Enum """

    def __init__(self, *args):
        self.args = args

    def __str__(self):
        return "Enumeration does not allow modification"

class EnumValueCompareError(ValueError, TypeError, EnumException):
    """ Raised when attempting to find a invalid type """

    def __init__(self, *args):
        self.args = args

    def __str__(self):
        return "Enumeration cannot compare the given values"


class EnumValue(object):
    _decamel = re.compile(r'[A-Z]*[^A-Z]*')

    """ A specific value of an enumerated type """

    def __init__(self, enumtype, index, key):
        """ Set up a new instance """
        self.__enumtype = enumtype
        self.__index = index
        self.__key = key
        self.__label = ' '.join(filter(None, self._decamel.findall(str(self))))

    @property
    def enumtype(self):
        return self.__enumtype

    @property
    def label(self):
        return self.__label

    @property
    def key(self):
        return self.__key

    @property
    def index(self):
        return self.__index

    def __str__(self):
        return "%s" % (self.key)

    def __int__(self):
        return int(self.index)

    def __repr__(self):
        return "EnumValue(%s, %s, %s)" % (
            repr(self.__enumtype),
            repr(self.__index),
            repr(self.__key),
        )

    def __hash__(self):
        return hash(self.__index)

    def __cmp__(self, other):
        result = NotImplemented
        #self_type = self.enumtype
        try:
            #assert self.enumtype == other.enumtype
            result = cmp(self.index, other.index) if isinstance( other, EnumValue ) else cmp(self.index, type(self.index)(other))
        except (AssertionError, AttributeError, ValueError):
            result = NotImplemented

        return result


class Enum(object):
    """ Enumerated type
    An enumeration object is created with a sequence of string arguments
    to the Enum() constructor::

        >>> from utils.datastructures import Enum
        >>> Colours = Enum('red', 'blue', 'green')
        >>> Weekdays = Enum('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
        >>> CompositeColors = Enum(Pink=8, Purple=10)

    The return value is an immutable sequence object with a value for each
    of the string arguments. Each value is also available as an attribute
    named from the corresponding string argument::

        >>> pizza_night = Weekdays[4]
        >>> shirt_colour = Colours.green

    The values are constants that can be compared only with values from
    the same enumeration; comparison with other values will invoke
    Python's fallback comparisons::

        >>> pizza_night == Weekdays.fri
        True
        >>> shirt_colour > Colours.red
        True
        >>> shirt_colour == "green"
        False

    Each value from an enumeration exports its sequence index
    as an integer, and can be coerced to a simple string matching the
    original arguments used to create the enumeration::

        >>> str(pizza_night)
        'fri'
        >>> shirt_colour.index
        2
    """

    def __extract(self, src, field, default):
        ret = src.get(field)
        if ret != None : src.__delitem__(field)
        else: ret = default
        return ret

    def __init__(self, *keys, **kwargs):
        """ Create an enumeration instance """

        #next_value function
        next_value = self.__extract(kwargs, 'next_value', lambda x: x + 1)
        #key_type type
        value_type = self.__extract(kwargs, 'value_type', EnumValue)
        #key_type type
        key_type = self.__extract(kwargs, 'key_type', int)
        #start_from value
        start_from = self.__extract(kwargs, 'start_from', 1)
        super(Enum, self).__setattr__('_empty_value', self.__extract(kwargs, 'empty_value', ''))
        super(Enum, self).__setattr__('_empty_text', self.__extract(kwargs, 'empty_text', ''))
        super(Enum, self).__setattr__('_sorted', SortedDict())
        super(Enum, self).__setattr__('_option_sorted',SortedDict)

        values = {}
        if keys:
            # key is the accessor
            # index is saved in database
            # value is the display value
            keys = tuple(keys)

            index = start_from
            for key in keys:
                enum_value = value_type(self, index, key)
                values[index] = enum_value
                self._sorted[index] = enum_value.label
                #self._option_sorted[index] = dict(id=index,text=enum_value.label)
                index = next_value(index)
                super(Enum, self).__setattr__(key, enum_value)
        elif kwargs:
            keys = tuple(kwargs)

            for key, index in kwargs.iteritems():
                enum_value = value_type(self, index, key)
                values[index] = enum_value
                self._sorted[index] = enum_value.label
                #self._option_sorted[index] = dict(id=index,text=enum_value.label)
                super(Enum, self).__setattr__(key, enum_value)
        else:
            raise EnumEmptyError()

        super(Enum, self).__setattr__('_keys', keys)
        super(Enum, self).__setattr__('_values', values)
        super(Enum, self).__setattr__('_key_type', key_type)
        super(Enum, self).__setattr__('_value_type', value_type)

    def __setattr__(self, name, value):
        raise EnumImmutableError(name)

    def __delattr__(self, name):
        raise EnumImmutableError(name)

    def __len__(self):
        return len(self._values)

    def __getitem__(self, index):
        return self._values[int(index) if isinstance(index, str) and index.isdigit() else index]

    def __setitem__(self, index, value):
        raise EnumImmutableError(index)

    def __delitem__(self, index):
        raise EnumImmutableError(index)

    def __iter__(self):
        return iter(self._values)

    def getValue(self, key):
        for v in self._values.itervalues():
            if v.key == key:
                return v
        raise EnumBadKeyError(key)

    def _insert_empty_item(self, sorted_dict, empty=False, all=False):
        if empty:
            sorted_dict.insert(0, self._empty_value, '')
        elif all:
            sorted_dict.insert(0, self._empty_value, 'All')
        return sorted_dict

    def dict(self, start=None, end=None, ignore=(), empty=False, all=False):
        if not (start or end or ignore):
            newdict = copy.deepcopy(self._sorted)
            self._insert_empty_item(newdict, empty=empty, all=all)
            return newdict

        if isinstance(ignore, str) or not isinstance(ignore, collections.Iterable):
            ignore = [ignore]

        if start is not None:
            start = self._sorted.keyOrder.index(start)
        if end is not None:
            end = self._sorted.keyOrder.index(end) + 1

        newdict = SortedDict()
        for k, v in self._sorted.items()[start:end]:
            if k not in ignore:
                newdict[k] = v

        self._insert_empty_item(newdict, empty=empty, all=all)
        return newdict

    def option_list(self, start=None, end=None, ignore=(), empty=False, all=False):
        if not (start or end or ignore):
            newdict = copy.deepcopy(self._sorted)
            self._insert_empty_item(newdict, empty=empty, all=all)
            return [dict(id=key,text=value) for key,value in newdict.iteritems()]

        if isinstance(ignore, str) or not isinstance(ignore, collections.Iterable):
            ignore = [ignore]

        if start is not None:
            start = self._sorted.keyOrder.index(start)
        if end is not None:
            end = self._sorted.keyOrder.index(end) + 1

        newdict = SortedDict()
        for k, v in self._sorted.items()[start:end]:
            if k not in ignore:
                newdict[k] = v

        self._insert_empty_item(newdict, empty=empty, all=all)
        return [dict(id=key,text=value) for key,value in newdict.iteritems()]

    def __contains__(self, index):
        return (int(index) if isinstance(index, str) else index) in self._values

