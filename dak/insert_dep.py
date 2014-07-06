#!/usr/bin/env python
'''
Creates a table called bin_dep11 with columns package(id) and dep11
'''
from daklib.dbconn import *

class depobject():

    def __init__(self):
        self._session = DBConn().session()

    def insertdata(self,binid,yamldoc):
        d = {"bin_id":binid,"yaml_data":yamldoc}
        sql = "INSERT into bin_dep(binary_id,metadata) VALUES (:bin_id, :yaml_data)"
        self._session.execute(sql,d)
        
    def close(self):
        self._session.close()

#for testing
if __name__ == "__main__":
    dobj = depobject()
    dobj.insertdata(555,"test data test data")
    dobj._session.commit()
    dobj.close()
    #session = DBConn().session()
    
