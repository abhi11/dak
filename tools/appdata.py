#!/usr/bin/env python
'''Checks binaries with a .desktop file or an appdata-xml file.
   Generates a dict with package name and associated appdata in 
   a list as value.'''

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class appdata:
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
        self._deskdic = {}
        self._xmldic = {}
        self._commdic = {}
        

    def create_session(self,connstr):
        ''' Establishes a session if it is not initialized during __init__. '''
        if connstr:
            engine = create_engine(connstr)
            Session = sessionmaker(bind=engine)
            return Session()
        else:
            print "Connection string invalid!"
            return None
            
    def find_desktop(self,session = None):
        ''' Find binaries with a .desktop file. '''
        if session:
            self._session = session
        #SQL logic:
        #select all the binaries that have a .desktop file

        sql = '''SELECT bc.file ,b.package from binaries b, bin_contents bc 
        where bc.file like 'usr/share/applications/%.desktop' and b.id = bc.binary_id'''

        result = self._session.execute(sql)
        rows = result.fetchall()
        #create a dict with package:[.desktop files]
        for r in rows:
            try:
                self._deskdic[str(r[1])].append(str(r[0]))
            except KeyError:
                self._deskdic[str(r[1])] = [str(r[0])]

    def find_xml(self,session = None):
        ''' Find binaries with a .xml file. '''

        if session:
            self._session = session
        #SQL logic:
        #select all the binaries that have a .xml file

        sql = '''SELECT bc.file ,b.package from binaries b, bin_contents bc 
        where bc.file like 'usr/share/appdata/%.xml' and b.id = bc.binary_id'''

        result = self._session.execute(sql)
        rows = result.fetchall()
        #create a dict with package:[.xml files]
        for r in rows:
            try:
                self._xmldic[str(r[1])].append(str(r[0]))
            except KeyError:
                self._xmldic[str(r[1])] = [str(r[0])]

    def comb_appdata(self):
        ''' Combines both dictionaries and creates a new list with all the metdata
        (i.e the .desktop as well as .xml files. '''

        #copy the .desktop files dict
        self._commdic = self._deskdic

        for key,li in self._xmldic.iteritems():
            #if package already in list just append the xml files
            try:
                self._commdic[key] += li
            #else create a new entry for the package
            except KeyError:
                self._commdic[key] = li

    def printfiles(self):
        ''' Prints the commdic '''
        for k,l in self._commdic.iteritems():
            print k +': ',l

if __name__ == "__main__":
    ap = appdata('postgresql+psycopg2://postgres:postgres@localhost/projectc')
    ap.find_desktop()
    ap.find_xml()
    ap.comb_appdata()
    ap.printfiles()
