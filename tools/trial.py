#!/usr/bin/env python

## Trial code. Checks the apper deb package for appdata xml

from apt import debfile 
import lxml.etree as et

x = debfile.DebPackage('apper_0.8.2-2_alpha.deb')
lof = x.filelist
for meta_file in lof:
    #change to regex
    if 'xml' in meta_file:
        xml_content = str(x.data_content(meta_file))


root = et.fromstring(xml_content)

dic = {'Type':root.attrib['type']}

for subs in root:
    if subs.tag == 'id':
        dic.update({'ID':subs.text})

    elif subs.tag == "description":
        desc = xml_content[xml_content.find('<description>'):xml_content.find('</description>')]
        desc = desc.replace('<description>','')
        dic.update({'Description':desc})

    #does the screenshots well but needs to be more generalised
    elif subs.tag == "screenshots":
        dic['Screenshots'] = {}
        for shots in subs:
            attr_dic = shots.attrib
            dic['Screenshots'].update({attr_dic['type']:[{'width': attr_dic['width']},{'height': attr_dic['height']},{'url':shots.text}]})

    elif subs.tag == "provides":
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

    elif subs.tag == "url":
        try:
            dic["Url"].update({subs.attrib['type'].title():subs.text})
        except KeyError:
            dic["Url"] = {subs.attrib['type'].title():subs.text}

                
    else:
        dic[subs.tag.title()]=subs.text

#Work with the dic to create yml
print dic
