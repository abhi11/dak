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

    def read_desktop(self,dcontent,compdata):
        '''
        Parses a .desktop file and sets ComponentData properties
        '''
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
                        compdata.ignore = True
                        
                    if key == 'Type' and value != 'Application':
                        compdata.ignore = True
                    else:
                        compdata.typ = 'Application'

                    if key.startswith('Name') :
                        if key[4:] == '':
                            if compdata.name:
                                if value not in compdata.name.values():
                                    compdata.name.update({'C':value})
                            else:
                                compdata.name = {'C':value}
                        else:
                            if compdata.name:
                                if value not in compdata.name.values():
                                    compdata.name.update({key[5:-1]:value})
                            else:
                                compdata.name = {key[5:-1]:value}
                                                    
                    if key == 'Categories':
                        value = value.split(';')
                        value.pop()
                        compdata.categories = value

                    if key.startswith('Comment'):
                        if key[7:] == '':
                            if compdata.summary:
                                if value not in compdata.summary.values():
                                    compdata.summary.update({'C':value})
                            else:
                                compdata.summary = {'C':value}
                        else:
                            if compdata.summary:
                                if value not in compdata.summary.values():
                                    compdata.summary.update({key[8:-1]:value})
                            else:
                                compdata.summary = {key[8:-1]:value}

                    if 'Keywords' in key:
                        if key[8:] == '':
                            if compdata.keywords:
                                if value not in compdata.keywords.values():
                                    compdata.keywords.update({'C':value})
                            else:
                                compdata.keywords = {'C':value}
                        else:
                            if compdata.keywords:
                                if value not in compdata.keywords.values():
                                    compdata.keywords.update({key[9:-1]:value})
                            else:
                                compdata.keywords = {key[9:-1]:value}
                                                
                    if key == 'MimeType':
                        val_list = value[0:-1].split(';')
                        compdata.mimetypes = val_list

                    if 'Architectures' in key:
                        val_list = value.split(',')
                        compdata.archs = val_list

                    if key == 'Icon':
                        compdata.icon = value
                        
                except:
                    pass

    def read_xml(self,xml_content,compdata):
        '''
        Reads the appdata from the xml file in usr/share/appdata.
        Sets ComponentData properties
        '''
        root = et.fromstring(xml_content)
        for key,val in root.attrib.iteritems():
            if key == 'type':
                compdata.typ = root.attrib['type']
    
        for subs in root:
            if subs.tag == 'id':
                compdata.ID = subs.text

            if subs.tag == "description":
                desc = xml_content[xml_content.find('<description>'):xml_content.find('</description>')]
                desc = desc.replace('<description>','')
                desc = desc.strip()
                desc = " ".join(desc.split())
                compdata.description = desc

            #does the screenshots well
            if subs.tag == "screenshots":
                compdata.screenshots = []
                for shots in subs:
                    attr_dic = shots.attrib
                    for k in attr_dic.iterkeys():
                        compdata.screenshots.append({k:make_num(attr_dic[k])})
                    compdata.screenshots.append({'url':shots.text})

            #needs changes provide's a bit tricky !!
            if subs.tag == "provides":
                compdata.provides = {}
                for bins in subs:
                    if bins.tag == "binary":
                        try : 
                            compdata.provides['binaries'].append(bins.text)
                        except KeyError:
                            compdata.provides['binaries']=[bins.text]
                    if bins.tag == 'library':
                                try : 
                                    compdata.provides['libraries'].append(bins.text)
                                except KeyError:
                                    compdata.provides['libraries']=[bins.text]           
                                                                                                        
            if subs.tag == "url":
                if compdata.url:
                    compdata.url.append({subs.attrib['type'].title():subs.text})
                else:
                    compdata.url = [{subs.attrib['type'].title():subs.text}]

            if subs.tag == "project_license":
                compdata.project_license = subs.text

            if subs.tag == "project_group":
                compdata.project_group = subs.text

    def read_metadata(self,component,binid,filelist,pkg):
        '''
        Reads the metadata from the xml file and the desktop files.
        And returns a list of ComponentData objects.
        '''
        component_list = []
        #Reading xml files and associated .desktop
        try:
            for meta_file in self._loxml:
                compdata = ComponentData(component,binid,self._filename,filelist,pkg)
                xml_content = str(self._deb.data_content(meta_file))
                self.read_xml(xml_content,compdata)
                #Reads the desktop files associated with the xml file
                if( '.desktop' in compdata.ID):
                    for dfile in self._lodesk:
                        #for desktop file matching the ID
                        if compdata.ID in dfile :
                            ID = compdata.ID
                            dcontent = self._deb.data_content(dfile)
                            self.read_desktop(dcontent,compdata)
                            #overwriting the Type field of .desktop by xml
                            compdata.ID = ID
                            if not compdata.ignore:
                                component_list.append(compdata)
                            self._lodesk.remove(dfile)
        except TypeError:
            print 'xml list is empty for the deb '+ self._filename

        #Reading the desktop files other than the file which matches the id in the xml file
        try:
            for dfile in self._lodesk:
                compdata = ComponentData(component,binid,self._filename,filelist,pkg)
                dcontent = self._deb.data_content(dfile)
                self.read_desktop(dcontent,compdata)
                if not compdata.ignore:
                    compdata.ID = self.find_id(dfile)
                    component_list.append(compdata)
        except TypeError:
            print 'desktop list is empty for the deb '+ self._filename
                        
        return component_list

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

        #properties
        self._ignore = False
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
        self._project_license = None
        self._project_group = None

    @property
    def ignore(self):
        return self._ignore
    @ignore.setter
    def ignore(self,val):
        self._ignore = val

    @property
    def ID(self):
        return self._ID       
    @ID.setter
    def ID(self,val):
        self._ID = val

    @property
    def typ(self):
        return self._type
    @typ.setter
    def typ(self,val):
        self._type = val
        
    @property
    def name(self):
        return self._name
    @name.setter
    def name(self,val):
        self._name = val
            
    @property
    def categories(self):
        return self._categories
    @categories.setter
    def icon(self,val):
        self._categories = val
                
    @property
    def icon(self):
        return self._icon
    @icon.setter
    def icon(self,val):
        self._icon = val
       
    @property
    def summary(self):
        return self._summary
    @summary.setter
    def summary(self,val):
        self._summary = val
             
    @property
    def description(self):
        return self._description
    @description.setter
    def description(self,val):
        self._description = val

    @property
    def screenshots(self):
        return self._screenshots
    @screenshots.setter
    def screenshots(self,val):
        self._screenshots = val
            
    @property
    def keywords(self):
        return self._keywords
    @keywords.setter
    def keywords(self,val):
        self._keywords = val
                    
    @property
    def archs(self):
        return self._archs
    @archs.setter
    def archs(self,val):
        self._archs = val
            
    @property
    def mimetypes(self):
        return self._mimetypes
    @mimetypes.setter
    def mimetypes(self,val):
        self._mimetypes = val

    @property
    def provides(self):
        return self._provides
    @provides.setter
    def mimetypes(self,val):
        self._provides = val

    @property
    def url(self):
        return self._url
    @url.setter
    def url(self,val):
        self._url = val

    @property
    def project_license(self):
        return self._project_license
    @project_license.setter
    def mimetypes(self,val):
        self._project_license = val

    @property
    def project_group(self):
        return self._project_group
    @project_group.setter
    def project_group(self,val):
        self._project_group = val
      
    def serialize_to_dic(self):
        ''' 
        Return a dic with all the properties
        '''
        dic = {}
        if self.ID:
            dic['ID'] = self.ID
        if self.typ:
             dic['Type'] = self.typ
        if self.name:
             dic['Name'] = self.name
        if self.categories:
            dic['Categories'] = self.categories
        if self.description:
            dic['Description'] = self.description
        if self.icon:
            dic['Icon'] = self.icon
        if self.keywords:
            dic['Keywords'] = self.keywords
        if self.summary:
            dic['Summary'] = self.summary
        if self.screenshots:
            dic['Screenshots'] = self.screenshots
        if self.archs:
            dic['Architectures'] = self.archs
        if self.mimetypes:
            dic['MimeTypes'] = self.mimetypes
        if self.url:
            dic['Url'] = self.url
        if self.provides:
            dic['Provides'] = self.provides
        if self.project_license:
            dic['ProjectLicense'] = self.project_license
        if self.project_group:
            dic['ProjectGroup'] = self.project_group
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
        
    def write_meta(self,ofile,dep11):
        '''
        Saves Appstream metadata in yaml format and also invokes the fetch_store function.
        '''
        metadata = yaml.dump(self._cdata.serialize_to_dic(),default_flow_style=False,
                             explicit_start=True,explicit_end=False,width=100,indent=4)
        ofile.write(metadata)
        dep11.insertdata(self._cdata._binid,metadata)
        dep11._session.commit()

    def fetch_screenshots(self):
        '''
        Fetches screenshots from the given url and stores it in png format.
        '''
        if self._cdata.screenshots:
            cnt = 1
            success = []
            for shot in self._cdata.screenshots:
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
                    success.append(True)
                except:
                    success.append(False)
            return any(success)
            
        #don't ignore metadata if screenshots itself is not present
        return True

    def fetch_icon(self):
        '''
        Searches for icon if aboslute path to an icon
        is not given. Component with invalid icons are ignored
        '''
        if self._cdata.icon:
            icon = self._cdata.icon
            if icon.endswith('.xpm') or icon.endswith('.tiff'):
                return False

            if icon[1:] in self._cdata._filelist:
                return save_icon(icon,self._cdata.ID,self._cdata._file)
                 
            else:
                ext_allowed = ('.png','.svg','.ico','.xcf','.gif','.svgz')
                for path in self._cdata._filelist:
                    if path.endswith(ext_allowed):
                        if 'pixmaps' in path or 'icons' in path:
                            return save_icon('/'+path,self._cdata.ID,self._cdata._file)

                ficon = findicon(self._cdata._pkg,icon,self._cdata._binid)
                flist = ficon.queryicon()
                ficon.close()
                
                if flist:
                    filepath = Config()["Dir::Pool"]+self._cdata._component+'/'+flist[1]
                    return save_icon('/'+flist[0],self._cdata.ID,filepath)
                return False

        #keep metadata if Icon self itself is not present
        return True

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
            screen_bool = cg.fetch_screenshots()
            icon_bool = cg.fetch_icon()
            if screen_bool or icon_bool:
                cg.write_meta(ofile,dep11)
        writer.close()
        dep11.close()


###Utility methods
def save_icon(icon,ID,filepath):
    '''
    Extracts the icon from the deb package and stores it.
    '''
    try:
        check_call("dpkg --fsys-tarfile {0} | tar xOf - .{1} > {2}/{3}.png".format(filepath,icon,Config()["Dir::Icon"],ID),
                    shell=True,stdout=logfile,stderr=logfile)
        print "Saved icon...."
        return True
    except CalledProcessError:
        return False

def make_icon_tar(location,component):
    '''
     Icons-%(component).tar.gz of each Component.
    '''
    for filename in glob.glob(location+"*.png"):
        call(["tar","-uvf","{0}Icons-{1}.tar".format(location,component),filename],stdout=logfile,stderr=logfile)
        call(["rm","-rf",filename],stdout=logfile,stderr=logfile)
    call(["gzip","-f","{0}Icons-{1}.tar".format(location,component)])

def loop_per_component(component,suitename=None):
    '''
    Run by main to loop for different component and architecture.
    '''
    path = Config()["Dir::Pool"]
    datalist = appdata()
    datalist.find_desktop(component=component,suitename=suitename)
    datalist.find_xml(component=component,suitename=suitename)
    datalist.close()

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
    comp_list = ('contrib')#,'main','non-free')
    for component in comp_list:
        loop_per_component(component,suitename)

    #close log file
    logfile.close()

if __name__ == "__main__":
    main()
