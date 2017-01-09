__author__ = 'Azharul'

import sqlalchemy as sa
from sqlalchemy import orm
from django.conf import settings


DBEngin = settings.DATABASES['default']['ENGINE'].rpartition('.')[-1]

connection_string = ('{0}://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}').format(DBEngin, **settings.DATABASES['default'])
if DBEngin == 'mysql':
    connection_string += '?charset=utf8'

metaData = sa.MetaData()
engine = sa.create_engine(connection_string, pool_recycle=3600, pool_size=20, max_overflow=-1)
metaData.bind = engine
engine.echo = False


session_maker = sa.orm.sessionmaker(bind=engine, autoflush=False)



def create_session():
    return sa.orm.scoped_session(session_maker)