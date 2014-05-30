#!/usr/bin/env python

## Trial code. Checks the apper deb package for appdata xml

from apt import debfile 
import xml.etree.ElementTree as et
from xml import etree

x = debfile.DebPackage('apper_0.8.2-2_alpha.deb')
lof = x.filelist
for control_file in lof:
    if 'xml' in control_file:
        xml_content = x.data_content(control_file) 
root = et.fromstring(xml_content)
of = open("com.yml","w")
dic = root.attrib
of.write("Type: "+dic['type'])
of.write("\n")

#tree traversal, better formatting needed
def recurseprint(subs):
    for psubs in subs:
        of.write("<"+psubs.tag+">"+psubs.text)
        recurseprint(psubs)
        of.write("</"+psubs.tag+">\n")

for subs in root:
    if subs.tag == 'id':
        of.write("ID: "+subs.text)
        of.write("\n")

    elif subs.tag == "description":
        of.write("Description: \n")
        recurseprint(subs)

    #does the screenshots well but needs to be more generalised
    elif subs.tag == "screenshots":
        for shots in subs:
            dic = shots.attrib
            of.write("Screenshots: \n")
            of.write("   "+dic['type']+":\n")
            of.write("      width: "+dic['width']+"\n")
            of.write("      height: "+dic['height']+"\n")            
            of.write("      url: "+shots.text+"\n")
        
    else:
        of.write("\n")
        of.write(subs.tag.title()+": "+subs.text)
        of.write("\n")

of.close()
