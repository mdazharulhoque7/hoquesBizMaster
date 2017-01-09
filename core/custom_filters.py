__author__ = 'Md. Azharul Hoque'

def get_name_list(name):
    """
    split name in the form of Model.field and Model-XX.field
    """
    name_list = []
    for i in name.split('.'):
        splitted = i.split('-')
        if len(splitted) == 2:
            name_list.append(splitted[0])
            name_list.append(int(splitted[1]) if splitted[1][0] != 'X' else splitted[1])
        elif len(splitted) == 1:
            name_list.append(splitted[0])
        else:
            raise Exception('name is in invalid format')
    return name_list

def extract_value(name_list=[],data_dict={}):
    value = data_dict
    for name in name_list:

        if name in value.keys():
            value = value.get(name)
            print(value)
        else:
            value = ''
            break
    return value


def extractFormFieldValue(data_dict={}, field_name=None):
    if not data_dict:
        data_dict = {}
    name_list = get_name_list(field_name)
    return extract_value(name_list,data_dict)

def extractFormFieldError(error_dict={}, field_name=None):
    if not error_dict:
        error_dict = {}
    name_list = get_name_list(field_name)
    return extract_value(name_list,error_dict)
