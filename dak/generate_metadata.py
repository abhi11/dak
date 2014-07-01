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
from check_appdata import appdata
from daklib.daksubprocess import call
from daklib.filewriter import ComponentDataFileWriter
from daklib.config import Config
from insert_dep import depobject

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
        
class ComponentData:
    '''
    Takes a dict containing the metadata. Sets a unique name for the object 
    which is same as the ID of the data.
    '''

    def __init__(self,dic):

        self._data = dic
        self._ID = ''

    def set_id(self,ID):
        '''
        Sets ID for the ComponentData.
        '''
        self._ID = ID

class MetaDataExtractor:

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
        #Handles MimeType Keywords Comment Name
        contents = {}
        lines = dcontent.splitlines()
                
        for line in lines:
            #first check if line is a comment
            line = self.notcomment(line)
            print line
            if line:
                #spliting into key-value pairs
                tray = line.split("=",1)
                print tray
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
                                contents['Name'].append({'C':value})
                            except KeyError:
                                contents['Name'] = [{'C':value}]
                        else:
                            try:
                                contents['Name'].append({key[5:-1]:value})
                            except KeyError:
                                contents['Name'] = [{key[5:-1]:value}]
                                                    
                    if key == 'Categories':
                        value = value.replace(';',',')
                        contents['Categories'] = value

                    if key.startswith('Comment'):
                        if key[7:] == '':
                            try:
                                contents['Summary'].append({'C':value})
                            except KeyError:
                                contents['Summary'] = [{'C':value}]
                        else:
                            try:
                                contents['Summary'].append({key[8:-1]:value})
                            except KeyError:
                                contents['Summary'] = [{key[8:-1]:value}]

                    if 'Keywords' in key:
                        if key[8:] == '':
                            try:
                                contents['Keywords'].append({'C':value})
                            except KeyError:
                                contents['Keywords'] = [{'C':value}]
                        else:
                            try:
                                contents['Keywords'].append({key[9:-1]:value})
                            except KeyError:
                                contents['Keywords'] = [{key[9:-1]:value}]
                                                
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

        return contents
        
    def read_xml(self,xml_content=None):
        '''
        Reads the appdata from the xml file in usr/share/appdata
        '''

        root = et.fromstring(xml_content)
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
                    if attr_dic['type']:
                        dic['Screenshots'].append({attr_dic['type']:[{'width': make_num(attr_dic['width'])},
                                                                                             {'height': make_num(attr_dic['height'])},{'url':shots.text}]})
                    else:
                        dic['Screenshots'].append({'notype':[{'width': make_num(attr_dic['width'])},
                                                                                             {'height': make_num(attr_dic['height'])},{'url':shots.text}]})

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

                
    def read_metadata(self):
        '''
        Reads the metadata from the xml file and the desktop files.
        And returns a list of ComponentData objects.
        '''

        cont_list = []
        #Readinf xml files and associated .desktop
        try:
            for meta_file in self._loxml:
                #change to regex
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
                            contents['Type'] = dic['Type']
                            dic.update(contents)
                            cd = ComponentData(dic)
                            cd.set_id(dic['ID'])
                            cont_list.append(cd)
                            self._lodesk.remove(dfile)
        except TypeError:
            print 'xml list is empty for the deb '+ self._filename

        #Reading the desktop files other than the file which matches the id in the xml file
        try:
            for dfile in self._lodesk:
                dcontent = self._deb.data_content(dfile)
                contents  = self.read_desktop(dcontent)
                print contents
                ID = self.find_id(dfile)
                cd = ComponentData(contents)
                cd.set_id(ID)
                cont_list.append(cd)
        except TypeError:
            print 'desktop list is empty for the deb '+ self._filename
                        
        return cont_list


class ContentGenerator:
    '''
    Takes list of ComponentData objects(python dicts as of now !). 
    And writes them into YAML format
    '''
    def __init__(self,comp_list,filename):

        self._list = comp_list
        self._file = filename
        
    def save_meta(self,ofile,binid,depobj):
        '''
        Saves Appstream metadata in yaml format and also invokes the fetch_store function.
        '''
        for data in self._list:
            metadata = yaml.dump(data._data,default_flow_style=False,explicit_start=False,explicit_end=True,width=100)
            ofile.write(metadata)
            print "printing metadata",data._data
            self.fetch_screenshots(data)
            self.fetch_icon(data)
            depobj.insertdata(binid,metadata)

    def fetch_screenshots(self,data):
        '''
        Fetches screenshots from the given url and stores it in png format.
        '''

        try:
            if data._data['Screenshots']:
                cnt = 1
                for shot in data._data['Screenshots']:
                    urllib.urlretrieve(shot[url],Config()["Dir::Export"]+data._ID+str(cnt)+'.png')
                    cnt = cnt + 1
                    print "Screenshots saved"
        except KeyError:
            pass

    def fetch_icon(self,data):
        try:
            icon = data._data['Icon']
            print icon
            l = self._file.split('/')
            print l
            deb = l.pop()
            ex_loc = "/".join(l)
            print ex_loc,self._file
            call(["dpkg","-x",self._file,ex_loc])
            icon_path = ex_loc+icon
            print icon_path
            #using a temp dir for now
            call(["cp",icon_path,"/home/abhishek/output/"+data._ID+".png"])
            print "Saved icon...."
            call(["rm","-rf",ex_loc+"/usr"])
        except KeyError:
            pass

def percomponent(component,suitename=None):
    path = '/home/abhishek/tanglu/pool/'
    datalist = appdata()
    values = {
        'suite': suitename,
        'component': component
    }

    datalist.find_desktop(component=component,suitename=suitename)
    datalist.find_xml(component=component,suitename=suitename)
    info_dic = datalist._infodic
    desk_dic = datalist._deskdic
    xml_dic = datalist._xmldic
    writer = ComponentDataFileWriter(**values)
    ofile = writer.open()
    depobj = depobject()

    for key in datalist._keylist:
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
            cd_list = mde.read_metadata()
            cg = ContentGenerator(cd_list,path+key)
            cg.save_meta(ofile,make_num(info_dic[key]),depobj)
            depobj._session.commit()
        except SystemError:
            print 'Not found !'
    ofile.close()
    depobj.close()
            
def main():
    if len(sys.argv) < 2 :
        usage()
        return

    suitename = sys.argv[1]
    comp_list = ['contrib','main','non-free']
    for component in comp_list:
        percomponent(component,suitename)

if __name__ == "__main__":
    main()
