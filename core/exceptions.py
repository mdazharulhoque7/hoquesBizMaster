__author__ = 'Azharul'

import re
import collections
from formencode import Invalid

class ResourceInsertException(Exception):
    """Raised when validation fails during save/update process. It wraps the
    original `formencode.Invalid` exception and contains reference to the Dao
    which raised the exception
    """
    _nested_msg_pattern = re.compile(r':\s?')   #: Pattern for splitting nested error message

    def __init__(self, e, resource):
        self.exception = e
        self.raiser = resource
        self.json_error = self.exception.error_dict
        self.prepare_json_error(self.json_error)

    def prepare_json_error(self,dict):
        for k, v in dict.iteritems():
            try:
                if isinstance(v, collections.Iterable):
                    print v
                    self.prepare_json_error(v)
                else:
                    if isinstance(v, Invalid):
                        dict[k] =  str(v)

            except Exception, e:
                print 'Error in --------Preparing Json ERROR'
                print e

    def grid_error(self, property=None, model_name=None):
        """For a given `property`, generates error list suitable for marking error
        fields in jqGrid.
        """
        if property:
            error_dict = self.exception.error_dict.get(model_name or self.raiser.model.__name__)
            if error_dict is None or getattr(error_dict.get(property), 'error_list', None) is None:
                return []

            error_list = [
                {} if row is None else dict.fromkeys(row.error_dict, True)
                for row in error_dict[property].error_list
            ]
        else:
            error_list = [{} if error_dict is None else dict.fromkeys(error_dict, True)
                          for error_dict in self.exception.error_list]

        return error_list

    def ajax_error(self, model_name=None):
        namespace = model_name or self.raiser.model.__name__
        return {namespace + '_' + k: getattr(v, 'message', v) for k, v in (self.exception.error_dict[namespace] or {}).iteritems()}

    @property
    def error_message(self):
        """If a single validation error occurred returns that error message,
        otherwise returns a common error message.
        """
        if sum(map(len, self.exception.error_dict.values())) > 1:
            return "Please correct the following errors"
        elif ':' in self.exception.msg:
            return self._nested_msg_pattern.split(self.exception.msg)[-1]

        return self.exception.msg

    def __repr__(self):
        return self.raiser.__class__.__name__ + " : Insert Exception "

    def __str__(self):
        return str(self.exception.error_dict)



class NotEditable(Exception):
    """Usually raised from Resource when it's impossible to perform a requested
    update/delete operation
    """
    pass

class UserDoesNotExistError(Exception):
    pass