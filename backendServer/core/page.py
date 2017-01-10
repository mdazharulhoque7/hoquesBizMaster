import math

def pagelimit(options, default_limit=None):
    try: page = int(options.get('page', 1))
    except: page = 1

    try: limit = int(options['rows']) if 'rows' in options else default_limit
    except: limit = default_limit
    
    return {'page': page, 'limit':limit}

class Page(object):
    def __init__(self, page, limit, records):
        self.page = int(page)
        self.limit = int(limit) if limit else records
        self.records = records
        self.rows = []
        self.total = int(math.ceil(float(self.records) / self.limit)) if records else 1
        
        if (self.page > self.total) or (self.page < 1):
            self.page = self.total

    def __str__(self):
        return 'page %s, total %s, records: %s\nrows %s' % (self.page, self.total, self.records, self.rows.__str__())
