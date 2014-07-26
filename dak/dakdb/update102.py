#!/usr/bin/env python

"""
Adds bin_dep table. Stores appstream metadata per binary
"""

import psycopg2
from daklib.dak_exceptions import DBUpdateError
from daklib.config import Config
from daklib.dbconn import *
statements = [
"""
CREATE TABLE bin_dep_try(id SERIAL PRIMARY KEY,
binary_id integer not null,
metadata text not null
);
""",

"""
ALTER TABLE bin_dep_try ADD CONSTRAINT binaries_bin_dep
FOREIGN KEY (binary_id) REFERENCES binaries (id) ON DELETE CASCADE;
"""
]
################################################################################

def do_update(self):
    print __doc__
    try:
        c = self.db.cursor()
        for stmt in statements:
            c.execute(stmt)
        self.db.commit()
    
    except psycopg2.ProgrammingError as msg:
    
        self.db.rollback()
        raise DBUpdateError('Unable to apply sick update 102, rollback issued. Error message: {0}'.format(msg))
