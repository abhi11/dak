#!/usr/bin/env python

'''
Takes a .deb file as an argument and reads the metadata from diffrent sources
such as the xml files in usr/share/appdata and .desktop files in usr/share/application.
Also created a screenshot cache and tarball of all the icons of packages beloging to a
given suite.
'''

from apt import debfile 
import lxml.etree as et
import yaml
import sys
import urllib
import glob
import sha
import datetime
from subprocess import CalledProcessError
from check_appdata import appdata,findicon
from daklib.daksubprocess import call,check_call
from daklib.filewriter import ComponentDataFileWriter
from daklib.config import Config
from insert_dep import DEP11Metadata

time_str = str(datetime.date.today())
logfile = open(Config()["Dir::log"]+"genmeta-{0}.txt".format(time_str),'w')

def usage():
    print """ Usage: dak generate_metadata suitename """

def make_num(s):
    '''
    Returns integer if the str is a digit
    else returns the str
    '''
    try:
        num = int(s)
        return num
    except ValueError:
        return s
                        
class MetaDataExtractor:
    '''
    Takes a deb file and extracts component metadata from it.
    '''

    def __init__(self,filename,xml_list = None,desk_list = None):
        '''
        Initialize the object with List of files.
        ''' 
        self._filename = filename
        self._deb = debfile.DebPackage(filename)
        self._loxml = xml_list
        self._lodesk = desk_list

    def notcomment(self,line=None):
        '''
        checks whether a line is a comment on .desktop file.
        '''
        line = line.strip()
        if line:
            if line[0]=="#":
                return None
            else:
                #when there's a comment inline
                if "#" in line:
                    line = line[0:line.find("#")]
                    return line
        return line

    def find_id(self,dfile=None):
        '''
        Takes an absolute path as a string and 
        returns the filename from the absolute path.
        '''
        li = dfile.split('/')
        return li.pop()

    def read_desktop(self,dcontent=None):
        '''
        Convert a .desktop file into a dict
        '''
        contents = {}
        lines = dcontent.splitlines()
                
        for line in lines:
            line = self.notcomment(line)
            if line:
                #spliting into key-value pairs
                tray = line.split("=",1)
                try:
                    key = str(tray[0].strip())
                    value = str(tray[1].strip())
                    #Ignore the file if NoDisplay is true
                    if key == 'NoDisplay' and value == 'True':
                        return None
                        
                    if key == 'Type' and value != 'Application':
                        return None
                    else:
                        contents['Type'] = 'Application'

                    if key.startswith('Name') :
                        if key[4:] == '':
                            try:
                                if value not in contents['Name'].values():
                                    contents['Name'].update({'C':value})
                            except KeyError:
                                contents['Name'] = {'C':value}
                        else:
                            try:
                                if value not in contents['Name'].values():
                                    contents['Name'].update({key[5:-1]:value})
                            except KeyError:
                                contents['Name'] = {key[5:-1]:value}
                                                    
                    if key == 'Categories':
                        value = value.split(';')
                        value.pop()
                        contents['Categories'] = value

                    if key.startswith('Comment'):
                        if key[7:] == '':
                            try:
                                if value not in contents['Summary'].values():
                                    contents['Summary'].update({'C':value})
                            except KeyError:
                                contents['Summary'] = {'C':value}
                        else:
                            try:
                                if value not in contents['Summary'].values():
                                    contents['Summary'].update({key[8:-1]:value})
                            except KeyError:
                                contents['Summary'] = {key[8:-1]:value}

                    if 'Keywords' in key:
                        if key[8:] == '':
                            try:
                                if value not in contents['Keywords'].values():
                                    contents['Keywords'].update({'C':value})
                            except KeyError:
                                contents['Keywords'] = {'C':value}
                        else:
                            try:
                                if value not in contents['Keywords'].values():
                                    contents['Keywords'].update({key[9:-1]:value})
                            except KeyError:
                                contents['Keywords'] = {key[9:-1]:value}
                                                
                    if key == 'MimeType':
                        val_list = value[0:-1].split(';')
                        contents['MimeTypes'] = val_list

                    if 'Architectures' in key:
                        val_list = value.split(',')
                        contents['Architectures'] = val_list

                    if key == 'Icon':
                        contents[key] = value
                        
                except:
                    pass
        try:
            if(contents['Icon']):
                return contents
        except KeyError:
            return None

    def read_xml(self,xml_content=None):
        '''
        Reads the appdata from the xml file in usr/share/appdata
        '''
        root = et.fromstring(xml_content)
        dic = {}
        #requires a fix here
        for key,val in root.attrib.iteritems():
            if key == 'type':
                dic = {'Type':root.attrib['type']}
    
        for subs in root:
            if subs.tag == 'id':
                dic.update({'ID':subs.text})

            if subs.tag == "description":
                desc = xml_content[xml_content.find('<description>'):xml_content.find('</description>')]
                desc = desc.replace('<description>','')
                desc = desc.strip()
                desc = " ".join(desc.split())
                dic.update({'Description':'  '+desc})

            #does the screenshots well
            if subs.tag == "screenshots":
                dic['Screenshots'] = []
                for shots in subs:
                    attr_dic = shots.attrib
                    for k in attr_dic.iterkeys():
                        dic['Screenshots'].append({k:make_num(attr_dic[k])})
                    dic['Screenshots'].append({'url':shots.text})

            #needs changes provide's a bit tricky !!
            if subs.tag == "provides":
                dic['Provides'] = {}
                for bins in subs:
                    if bins.tag == "binary":
                        try : 
                            dic['Provides']['binaries'].append(bins.text)
                        except KeyError:
                            dic['Provides']['binaries']=[bins.text]
                            if bins.tag == 'library':
                                try : 
                                    dic['Provides']['libraries'].append(bins.text)
                                except KeyError:
                                    dic['Provides']['libraries']=[bins.text]           
                                                                                                        
            if subs.tag == "url":
                try:
                    dic["Url"].append({subs.attrib['type'].title():subs.text})
                except KeyError:
                    dic["Url"] = [{subs.attrib['type'].title():subs.text}]

            if subs.tag == "project_license":
                dic['ProjectLicense'] = subs.text

            if subs.tag == "project_group":
                dic['ProjectGroup'] = subs.text

        return dic        

                
    def read_metadata(self,component,binid,filelist,pkg):
        '''
        Reads the metadata from the xml file and the desktop files.
        And returns a list of ComponentData objects.
        '''
        cont_list = []
        #Reading xml files and associated .desktop
        try:
            for meta_file in self._loxml:
                xml_content = str(self._deb.data_content(meta_file))
                dic = self.read_xml(xml_content)
                #Reads the desktop files associated with the xml file
                if( '.desktop' in dic["ID"]):
                    for dfile in self._lodesk:
                        #for desktop file matching the ID
                        if dic['ID'] in dfile :
                            dcontent = self._deb.data_content(dfile)
                            contents  = self.read_desktop(dcontent)
                            #overwriting the Type field of .desktop by xml
                            #Type attribute may not always be present
                            if contents:
                                try:
                                    contents['Type'] = dic['Type']
                                except KeyError:
                                    pass
                                dic.update(contents)

                            compdata = ComponentData(component,binid,self._filename,filelist,pkg)
                            compdata.set_props(dic)
                            cont_list.append(compdata)
                            self._lodesk.remove(dfile)
        except TypeError:
            print 'xml list is empty for the deb '+ self._filename

        #Reading the desktop files other than the file which matches the id in the xml file
        try:
            for dfile in self._lodesk:
                dcontent = self._deb.data_content(dfile)
                contents  = self.read_desktop(dcontent)
                if contents:
                    contents['ID'] = self.find_id(dfile)
                    compdata = ComponentData(component,binid,self._filename,filelist,pkg)
                    compdata.set_props(contents)
                    cont_list.append(compdata)
        except TypeError:
            print 'desktop list is empty for the deb '+ self._filename
                        
        return cont_list

class ComponentData:
    '''
    Used to store the properties of component data. Used by MetaDataExtractor
    '''
    def __init__(self,component,binid,filename,filelist,pkg):
        '''
        Used to set the properties to None.
        '''
        self._component = component
        self._filelist = filelist
        self._pkg = pkg
        self._binid = binid
        self._file = filename
        self._ID = None
        self._type = None
        self._name = None
        self._categories = None
        self._icon = None
        self._summary = None
        self._description = None
        self._screenshots = None
        self._keywords = None
        self._archs = None
        self._mimetypes = None
        self._provides = None
        self._url = None
        self._prjctlic = None
        self._prjctgrp = None
        
    def set_props(self,dic):
        '''
        Sets all the properties of a Componentdata
        '''
        try:
            self._ID = dic['ID']
        except KeyError:
            pass
        try:
            self._type = dic['Type']
        except KeyError:
            pass
        try:
            self._name = dic['Name']
        except KeyError:
            pass
        try:
            self._categories = dic['Categories']
        except KeyError:
            pass
        try:
            self._description = dic['Description']
        except KeyError:
            pass
        try:
            self._icon = dic['Icon']
        except KeyError:
            pass
        try:
            self._keywords = dic['Keywords']
        except KeyError:
            pass
        try:
            self._summary = dic['Summary']
        except KeyError:
            pass
        try:
            self._screenshots = dic['Screenshots']
        except KeyError:
            pass
        try:
            self._archs = dic['Architectures']
        except KeyError:
            pass
        try:
            self._mimetypes = dic['MimeTypes']
        except KeyError:
            pass
        try:
            self._url = dic['Url']
        except KeyError:
            pass
        try:
            self._provides = dic['Provides']
        except KeyError:
            pass
        try:
            self._prjctlic = dic['ProjectLicense']
        except KeyError:
            pass
        try:
            self._prjctgrp = dic['ProjectGroup']
        except KeyError:
            pass

    def serialize_to_dic(self):
        ''' 
        Return a dic with all the properties
        '''
        dic = {}
        if self._ID:
            dic['ID'] = self._ID 
        if self._type:
             dic['Type'] = self._type
        if self._name:
             dic['Name'] = self._type
        if self._categories:
            dic['Categories'] = self._categories
        if self._description:
            dic['Description'] = self._description
        if self._icon:
            dic['Icon'] = self._icon
        if self._keywords:
            dic['Keywords'] = self._keywords
        if self._summary:
            dic['Summary'] = self._summary
        if self._screenshots:
            dic['Screenshots'] = self._screenshots
        if self._archs:
            dic['Architectures'] = self._archs
        if self._mimetypes:
            dic['MimeTypes'] = self._mimetypes
        if self._url:
            dic['Url'] = self._url
        if self._provides:
            dic['Provides'] = self._provides
        if self._prjctlic:
            dic['ProjectLicense'] = self._prjctlic
        if self._prjctgrp:
            dic['ProjectGroup'] = self._prjctgrp
        return dic

class ContentGenerator:
    '''
    Takes a ComponentData object.And writes the metadat into YAML format
    Stores screenshot and icons.
    '''
    def __init__(self,compdata):
        '''
        List contains componendata of a archtype of a component
        '''
        self._cdata = compdata
        
    def save_meta(self,ofile,depobj):
        '''
        Saves Appstream metadata in yaml format and also invokes the fetch_store function.
        '''
        bool_shots = self.fetch_screenshots()
        bool_icon =  self.fetch_icon()
        if bool_shots or bool_icon :
            metadata = yaml.dump(self._cdata.serialize_to_dic(),default_flow_style=False,
                                 explicit_start=True,explicit_end=False,width=100,indent=4)
            ofile.write(metadata)
            depobj.insertdata(self._cdata._binid,metadata)

    def fetch_screenshots(self):
        '''
        Fetches screenshots from the given url and stores it in png format.
        '''
        if self._cdata._screenshots:
            cnt = 1
            for shot in self._cdata._screenshots:
                '''
                use sha hashing to name the screenshots
                '''
                try:
                    image = urllib.urlopen(shot['url']).read()
                    has = sha.new(image)
                    hd = has.hexdigest()
                    f = open(Config()["Dir::Export"]+self._cdata._pkg+'-'+hd+'.png','wb')
                    f.write(image)
                    f.close()
                    print "Screenshots saved..."
                    return True
                except KeyError:
                    pass
        return False

    def fetch_icon(self):
        '''
        Searches for icon if aboslute path to an icon
        is not given. Component with invalid icons are ignored
        '''
        try:
            icon = self._cdata._icon
            if icon.endswith('.xpm') or icon.endswith('.tiff'):
                return False

            if icon[1:] in self._cdata._filelist:
                return save_icon(icon,self._cdata._ID,self._cdata._file)
                 
            else:
                for path in self._cdata._filelist:
                    if path.endswith(icon+'.png') or path.endswith(icon+'.svg') or path.endswith(icon+'.ico')\
                       or path.endswith(icon+'.xcf') or path.endswith(icon+'.gif') or path.endswith(icon+'.svgz'):
                        if 'pixmaps' in path or 'icons' in path:
                            return save_icon('/'+path,self._cdata._ID,self._cdata._file)
                ficon = findicon(self._cdata._pkg,icon,self._cdata._binid)
                flist = ficon.queryicon()
                if flist:
                    filepath = Config()["Dir::Pool"]+self._cdata._component+'/'+flist[1]
                    return save_icon('/'+flist[0],self._cdata._ID,filepath)
                return False

        except KeyError:
            return False

class MetadataPool:
    '''
    Keeps a pool of component metadata per arch per component
    '''
    def __init__(self,values):
        '''
        Sets the archname of the metadata pool.
        '''
        self._values = values
        self._list = []

    def append_compdata(self,compdatalist):
        '''
        makes a list of all the componentdata objects in a arch pool
        '''
        self._list = self._list + compdatalist

    def saver(self):
        """
        Writes yaml doc, saves metadata in db and stores icons and screenshots
        """
        writer = ComponentDataFileWriter(**self._values)
        ofile = writer.open()
        dep11 = DEP11Metadata()
        for cdata in self._list:
            cg = ContentGenerator(cdata)
            cg.save_meta(ofile,dep11)
            dep11._session.commit()
        writer.close()
        dep11.close()


###Utility methods
def save_icon(icon,ID,filepath):
    '''
    Extracts the icon from the deb package and stores it.
    '''
    l = filepath.split('/')
    deb = l.pop()
    ex_loc = "/".join(l)
    call(["dpkg","-x",filepath,ex_loc],stdout=logfile,stderr=logfile)
    icon_path = ex_loc+icon
    try:
        check_call(["cp",icon_path,Config()["Dir::Icon"]+ID+".png"],stdout=logfile,stderr=logfile)
        print "Saved icon...."
        call(["rm","-rf",ex_loc+"/usr"])
        call(["rm","-rf",ex_loc+"/etc"])
        return True
    except CalledProcessError:
        call(["rm","-rf",ex_loc+"/usr"])
        call(["rm","-rf",ex_loc+"/etc"])
        print 'icon corrupted not saving metadata'
        return False

def make_icon_tar(location,component):
    '''
     Icons-%(component).tar.gz of each Component.
    '''
    for filename in glob.glob(location+"*.png"):
        call(["tar","-uvf","{0}Icons-{1}.tar".format(location,component),filename],stdout=logfile,stderr=logfile)
        call(["rm","-rf",filename],stdout=logfile,stderr=logfile)
    call(["gzip","-f","{0}Icons-{1}.tar".format(location,component)])

def percomponent(component,suitename=None):
    '''
    Run by main to loop for different component and architecture.
    '''
    path = Config()["Dir::Pool"]
    datalist = appdata()

    datalist.find_desktop(component=component,suitename=suitename)
    datalist.find_xml(component=component,suitename=suitename)
    info_dic = datalist._idlist
    desk_dic = datalist._deskdic
    xml_dic = datalist._xmldic
    pkg_list = datalist._pkglist

    for arch in datalist.arch_deblist.iterkeys():
        values = {
            'suite': suitename,
            'component': component,
            'architecture': arch
        }
        pool = MetadataPool(values)
        for key in datalist.arch_deblist[arch]:
            print 'Processing deb: ' + key
            try:
                xmlfiles = xml_dic[key]
            except KeyError:
                xmlfiles = None
                 
            try:
                deskfiles = desk_dic[key]
            except KeyError:
                deskfiles = None
            #loop over all_dic to find metadata of all the debian packages
            try:
                mde = MetaDataExtractor(path+key,xmlfiles,deskfiles)
                filelist = mde._deb.filelist
                cd_list = mde.read_metadata(component,make_num(info_dic[key]),filelist,pkg_list[key])
                pool.append_compdata(cd_list)
            except SystemError:
                print 'Not found !'

        #Save metadata of all binaries of the Component-arch
        pool.saver()
    make_icon_tar(Config()["Dir::Icon"],component)
    print "Done with component ",component
            
def main():
    if len(sys.argv) < 2 :
        usage()
        return

    suitename = sys.argv[1]
    comp_list = ['contrib','main','non-free']
    for component in comp_list:
        percomponent(component,suitename)
    #close log file
    logfile.close()

if __name__ == "__main__":
    main()
    
