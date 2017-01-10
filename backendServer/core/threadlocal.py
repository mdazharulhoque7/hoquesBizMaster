__author__ = 'Azharul'

import threading

from core.dbconfig import create_session

__all__ = ['get', 'set', 'cleanup', 'db_session', 'get_current_user', 'get_active_request']

tl = threading.local()

def get(key):
    return getattr(tl, key, None)

def set(key, value):
    setattr(tl, key, value)

def db_session():
    if get('session') is None:
        set('session', create_session())

    return get('session')

def get_current_user():
    return get('user')

def get_active_request():
    return get('request')

def cleanup():
    if hasattr(tl, 'session'):
        tl.session.remove()

    for k in dir(tl):
        if not k.startswith('__'):
            delattr(tl, k)

