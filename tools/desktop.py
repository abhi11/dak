#!/usr/bin/env python
'''Checks binaries with a .desktop file'''

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class desktop:
    def __init__(self,connstr=None):
        ''' Initialize the variables and make the connection '''
    
        if connstr:
            self._constr = connstr
            self._engine = create_engine(self._constr)
            Session = sessionmaker(bind=self._engine)
            self._session = Session()
        else:
            self._constr = ''
            self._engine = None
            self._session = None

    def create_session(self,connstr):
        ''' Establishes a session if it is not initialized during __init__. '''
        if connstr:
            engine = create_engine(connstr)
            Session = sessionmaker(bind=engine)
            return Session()
        else:
            print "Connection string invalid!"
            return None
            
    def find_bins(self,session = None):
        ''' Find binaries with a .desktop file. '''
        if session:
            self._session = session
        #SQL logic:
        #select all the binaries that have a .desktop file

        sql = '''SELECT bc.file ,b.package from binaries b, bin_contents bc 
        where bc.file like '%.desktop' and b.id = bc.binary_id'''
        result = self._session.execute(sql)
        rows = result.fetchall()
        for r in rows:
            print 'file: '+str(r[0])+ ' package: '+str(r[1])

if __name__ == "__main__":
    Desktop = desktop('postgresql+psycopg2://postgres:postgres@localhost/projectc')
    Desktop.find_bins(session)
            
        
        
        


