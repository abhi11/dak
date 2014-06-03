#!/usr/bin/env python

## Trial code. Checks the apper deb package for appdata xml

from apt import debfile 
import lxml.etree as et
import yaml

x = debfile.DebPackage('apper_0.8.2-2_alpha.deb')
lof = x.filelist
#print lof

def notcomment(line):
        line = line.strip()
        try:
                if line[0]=="#":
                        return None
                else:
                        #when there's a comment inline
                        if "#" in line:
                                line = line[0:line.find("#")]
                        return line
        except:
                return None

def read_desktop(dcontent):
        '''Convert a .desktop file into a dict'''
        ##change Name tag to Summary and make a list with different langs Name[lang]
        ## and also change the semi-colons in Categories to commas
        contents = {}
        lines = dcontent.splitlines()
        for line in lines:
                #first check if line is a comment
                line = notcomment(line)
                if line:
                    #spliting into key-value pairs
                    tray = line.split("=",1)
                    try:
                        contents[str(tray[0].strip())] = str(tray[1].strip())
                    except:
                        pass
        return contents
    

for meta_file in lof:
    #change to regex
    if 'xml' in meta_file:
        xml_content = str(x.data_content(meta_file))
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

            #does the screenshots well but needs to be more generalised
            if subs.tag == "screenshots":
                dic['Screenshots'] = {}
                for shots in subs:
                    attr_dic = shots.attrib
                    dic['Screenshots'].update({attr_dic['type']:[{'width': attr_dic['width']},{'height': attr_dic['height']},{'url':shots.text}]})

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
                    dic["Url"].update({subs.attrib['type'].title():subs.text})
                except KeyError:
                    dic["Url"] = {subs.attrib['type'].title():subs.text}

            if subs.tag == "project_license":
                dic['ProjectLicense'] = subs.text

            if subs.tag == "project_group":
                dic['ProjectGroup'] = subs.text
            
        if( '.desktop' in dic["ID"]):
            print dic["ID"]
            for dfile in lof:
                if '.desktop' in dfile :
                    print dfile
                    dcontent = x.data_content(dfile)
                    #print dcontent
                    dic.update(read_desktop(dcontent))

        #Work with the dic to create yml
        metadata = yaml.dump(dic,default_flow_style=False,explicit_start=False,width=100)
        ofile = open("com.yml","w")
        ofile.write(metadata)
        ofile.close()

#print dic
