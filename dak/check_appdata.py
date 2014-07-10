#!/usr/bin/env python
'''
Checks binaries with a .desktop file or an appdata-xml file.
Generates a dict with package name and associated appdata in 
a list as value.
'''
from daklib.dbconn import *
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class appdata:
    def __init__(self,connstr=None):
        '''
		Initialize the variables and make the connection
		'''
        if connstr:
            self._constr = connstr
            self._engine = create_engine(self._constr)
            Session = sessionmaker(bind=self._engine)
            self._session = Session()
        else:
            #using Config
            self._constr = ''
            self._engine = None
            self._session = DBConn().session()
        self._infodic = {}
        self._deskdic = {}
        self._xmldic = {}
        self._commdic = {}
        self.arch_deblist = {}
        
    def create_session(self,connstr):
        '''
		Establishes a session if it is not initialized during __init__.
		'''
        if connstr:
            engine = create_engine(connstr)
            Session = sessionmaker(bind=engine)
            return Session()
        else:
            print "Connection string invalid!"
            return None
            
    def find_desktop(self,component,session = None,suitename=None):
        '''
		Find binaries with a .desktop file.
		'''
        if session:
            self._session = session

        params = {
            'component' : component,
            'suitename' : suitename
            }
        #SQL logic:
        #select all the binaries that have a .desktop file
        sql = """SELECT distinct on (b.package) bc.file, f.filename, c.name, b.id, a.arch_string from binaries b, bin_contents bc , 
            bin_associations ba, suite s, files f, override o, component c, architecture a
            where b.type = 'deb' and bc.file like 'usr/share/applications/%.desktop' and b.id = bc.binary_id and
            b.file = f.id and o.package = b.package and c.id = o.component and c.name = :component
            and b.id = ba.bin and  b.architecture = a.id and ba.suite = s.id and s.suite_name = :suitename"""

        result = self._session.execute(sql,params)
        rows = result.fetchall()
        #create a dict with packagename:[.desktop files]
        for r in rows:
            key = str(r[2])+'/'+str(r[1])
            try:
                if key not in self.arch_deblist[str(r[4])]:
                    self._infodic[key] = str(r[3])
                    self.arch_deblist[str(r[4])].append(key)
            except KeyError:
                self.arch_deblist[str(r[4])] = [key]
                self._infodic[key] = str(r[3])
            try:
                if str(r[0]) not in self._deskdic[key]:
                    self._deskdic[key].append(str(r[0]))
            except KeyError:
                self._deskdic[key] = [str(r[0])]

    def find_xml(self,component,session = None,suitename = None):
        '''
		Find binaries with a .xml file.
		'''
        if session:
            self._session = session
        
        params = {
            'component' : component,
            'suitename' : suitename
            }
        #SQL logic:
        #select all the binaries that have a .xml file
        if suitename:
            sql = """SELECT distinct on (b.package) bc.file, f.filename, c.name, b.id, a.arch_string from binaries b, bin_contents bc , 
            bin_associations ba, suite s, files f,override o, component c, architecture a
            where b.type = 'deb' and bc.file like 'usr/share/appdata/%.xml' and b.id = bc.binary_id and 
            b.file = f.id and o.package = b.package and o.component = c.id and c.name = :component
            and b.id = ba.bin and b.architecture = a.id and ba.suite = s.id and s.suite_name = :suitename"""

        result = self._session.execute(sql,params)
        rows = result.fetchall()
        #create a dict with package:[.xml files]
        for r in rows:
            key = str(r[2])+'/'+str(r[1])
            try:
                if key not in self.arch_deblist[str(r[4])]:
                    self._infodic[key] = str(r[3])
                    self.arch_deblist[str(r[4])].append(key)
            except KeyError:
                self.arch_deblist[str(r[4])] = [key]
                self._infodic[key] = str(r[3])
            try:
                if str(r[0]) not in self._xmldic[key]:
                    self._xmldic[key].append(str(r[0]))
            except KeyError:
                self._xmldic[key] = [str(r[0])]

    def comb_appdata(self):
        '''
		Combines both dictionaries and creates a new list with all the metdata
        (i.e the .desktop as well as .xml files.
		'''
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
        '''
		Prints the commdic,
		'''
        for k,l in self._commdic.iteritems():
            print k +': ',l

#For testing
if __name__ == "__main__":

    for component in ['contrib','main','non-free']:
        ap = appdata()
        ap.find_desktop(component = component, suitename='aequorea')
        ap.find_xml(component = component, suitename='aequorea')
        ap.comb_appdata()
        ap.printfiles()
