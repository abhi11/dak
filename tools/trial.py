#!/usr/bin/env python

'''Takes a .deb file as an argument and reads the metadata from diffrent sources
   such as the xml files in usr/share/appdata and .desktop files in usr/share/
'''

from apt import debfile 
import lxml.etree as et
import yaml

def make_num(s):
        '''Returns integer if the str is a digit
        else returns the str'''
        try:
                num = int(s)
                return num
        except ValueError:
                return s
        


class Content:

        def __init__(self,filename):
                '''Initialize the object with List of files'''                
                self._deb = debfile.DebPackage(filename)
                self._lof = self._deb.filelist

        def notcomment(self,line=None):
                '''checks whether a line is a comment on .desktop file'''
                line = line.strip()
                if line:
                        if line[0]=="#":
                                return None
                        else:
                                #when there's a comment inline
                                if "#" in line:
                                        line = line[0:line.find("#")]
                                return line
                else:
                        return None

        def read_desktop(self,dcontent=None):
                '''Convert a .desktop file into a dict'''
                #Handles MimeType Keywords Comment Name

                contents = {}
                lines = dcontent.splitlines()
    
                for line in lines:
                        #first check if line is a comment
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
                ''' Reads the appdata from the xml file in usr/share/appdata '''

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
                                dic['Screenshots'] = {}
                                for shots in subs:
                                        attr_dic = shots.attrib
                                        dic['Screenshots'].update({attr_dic['type']:[{'width': make_num(attr_dic['width'])},
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
                '''Reads the metadata from the xml file and the desktop files.
                And returns a list of dict with the component data.'''

                cont_list = []
                for meta_file in self._lof:
                        #change to regex
                        if 'xml' in meta_file:
                                xml_content = str(self._deb.data_content(meta_file))
                                dic = self.read_xml(xml_content)
                                #Reads the desktop files associated with the xml file
                                if( '.desktop' in dic["ID"]):
                                        for dfile in self._lof:
                                                #for desktop file matching the ID
                                                if dic['ID'] in dfile :
                                                        dcontent = self._deb.data_content(dfile)
                                                        contents  = self.read_desktop(dcontent)
                                                        if contents :
                                                                #overwriting the Type field of .desktop by xml
                                                                contents['Type'] = dic['Type']
                                                                dic.update(contents)
                                                        cont_list.append(dic)

                                                elif '.desktop' in dfile :
                                                        dcontent = self._deb.data_content(dfile)
                                                        contents  = self.read_desktop(dcontent)
                                                        if contents:
                                                                cont_list.append(contents)
                                                else:
                                                        #if dfile is not a desktop file
                                                        continue
                return cont_list

if __name__ == "__main__":
        obj = Content('apper_0.8.2-2_alpha.deb')
        li_to_wr = obj.read_metadata()
        for dic in li_to_wr:
                yaml.dump(dic,default_flow_style=False,explicit_start=False,explicit_end=True,width=100)
