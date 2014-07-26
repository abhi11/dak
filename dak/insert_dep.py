#!/usr/bin/env python
"""
Inserts appstream metadata per binary.
"""
from daklib.dbconn import *

class DEP11Metadata():

    def __init__(self):
        self._session = DBConn().session()

    def insertdata(self,binid,yamldoc):
        d = {"bin_id":binid,"yaml_data":yamldoc}
        sql = "insert into bin_dep(binary_id,metadata) VALUES (:bin_id, :yaml_data)"
        self._session.execute(sql,d)
        
    def close(self):
        self._session.close()

#for testing
if __name__ == "__main__":
    dobj = DEP11Metadata()
    dobj.insertdata(555,"test data test data")
    dobj._session.commit()
    dobj.close()
    #session = DBConn().session()
    
