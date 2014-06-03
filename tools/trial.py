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
    #Handles MimeType Keywords Comment Name

    contents = {}
    lines = dcontent.splitlines()
    for line in lines:
        #first check if line is a comment
        line = notcomment(line)
        if line:
            #spliting into key-value pairs
            tray = line.split("=",1)
            try:
                key = str(tray[0].strip())
                value = str(tray[1].strip())
                
                if 'Name' in key:
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
                                
                elif key == 'Categories':
                    value = value.replace(';',',')
                    contents['Categories'] = value

                elif 'Comment' in key:
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

                elif 'Keywords' in key:
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
                    

                elif key == 'MimeType':
                    val_list = value[0:-1].split(';')
                    contents['MimeTypes'] = val_list

                else:
                    contents[key] = value

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
                    dic["Url"].append({subs.attrib['type'].title():subs.text})
                except KeyError:
                    dic["Url"] = [{subs.attrib['type'].title():subs.text}]

            if subs.tag == "project_license":
                dic['ProjectLicense'] = subs.text

            if subs.tag == "project_group":
                dic['ProjectGroup'] = subs.text
            
        if( '.desktop' in dic["ID"]):
            for dfile in lof:
                if '.desktop' in dfile :
                    dcontent = x.data_content(dfile)
                    #print dcontent
                    dic.update(read_desktop(dcontent))

        #Work with the dic to create yml
        metadata = yaml.dump(dic,default_flow_style=False,explicit_start=False,width=100)
        ofile = open("com.yml","w")
        ofile.write(metadata)
        ofile.close()

#print dic
