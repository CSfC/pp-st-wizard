#!/usr/bin/env python3
""" 
Module that converts PP xml documents to an HTML worksheet
"""

import base64
from io import StringIO 
import warnings
import sys
import xml.etree.ElementTree as ET
import PPObject


class PPMap:
    """ Structure that saves modules to their associated bases """

    ## These are the class fields

    # Maps a name to the base and module definitions.
    basenameToDefs={}

    # List of all modules
    modnameToDef={}


  
    def __init__(self):
        self.base=None
        self.modules=[]


    def add_mod(modobj, basetrees):
        """ Adds a module """
        name = modobj.root.attrib["name"]
        PPMap.modnameToDef[name]=modobj # Add to all modules
        for basetree in basetrees:
            basename = basetree.attrib["name"]
            baseMap = PPMap.get_pp_map(basename)
            baseMap.modules.append(modobj)          # Add it to the bases

    def get_pp_map(name):
        if not name in PPMap.basenameToDefs:
            PPMap.basenameToDefs[name]=PPMap()
        return PPMap.basenameToDefs[name]

    def write_init_pp_structures(out):
        out.write("function initPPStructures(){")
        out.write("}")

    def build_worksheet(out):
        out.write("<div id='ws_base'>")
        out.write("<h3>Select the Base Protection Profile:</h3>")
        modsec=""
        # Build the selection area for base PPs
        for name in sorted(PPMap.basenameToDefs):
            map=PPMap.basenameToDefs[name]
            if map.base == None:
                sys.err.print("Some module modifies an unknown base: "+name)
                del PPMap.basenameToDefs[name]
                continue
            id=PPObject.to_id(name)
            # THis will break if modules have a double quote in their name
            # Probably no risk of that.
            out.write("<input type='checkbox' class='basecheck' onchange='baseChange(this); return false;'")
            out.write("' id='bases:"+id+"'></input>")
            out.write(name+ " ")
            out.write(map.base.root.find("./cc:PPReference/cc:ReferenceTable/cc:PPVersion",PPObject.ns).text+ "<br/>\n")
            # for module in map.modules:
        out.write("</div>\n")
        
        out.write("<div id='ws_mods' class='disabled");
        
        for base in PPMap.basenameToDefs:
            out.write(" dep:")
            out.write(PPObject.to_id(base))
        out.write("'>")
        out.write("<h3>Select All Applicable Modules</h3>\n")
        # Run through all modules
        for name in sorted(PPMap.modnameToDef):
            mod=PPMap.modnameToDef[name]
            id=PPObject.to_id(name)
            out.write("<div class='hidable modcheckdiv")
            for base in mod.root.findall(".//cc:base-pp",  PPObject.ns):
                out.write(" dep:")
                out.write(PPObject.to_id(base.attrib["name"]))
            out.write("'>")
            out.write("<input type='checkbox' class='modcheck' onchange='moduleChange()' id='mods:"+id+"'></input>")
            out.write(name + " ")
            out.write(mod.root.find("./cc:PPReference/cc:ReferenceTable/cc:PPVersion",PPObject.ns).text+ "<br/>\n")
            out.write("</div>\n")


        out.write("</div>") # Ends ws_mods

        # Run through all the bases
        for name in sorted(PPMap.basenameToDefs):
            map=PPMap.basenameToDefs[name]
            id=PPObject.to_id(name)
            out.write("<div class='hidable dep:"+id+"' id='base:"+id+"'>");
            out.write("<h3>"+name+"</h3>")
            obj = map.base
            out.write(obj.handle_contents(obj.root, False))
            out.write("</div>")

        # Run through all the modules
        for name in sorted(PPMap.modnameToDef):
            mod=PPMap.modnameToDef[name]
            id=PPObject.to_id(name)
            out.write("<div class='hidable dep:"+id + "'>");
            out.write("<h3>"+mod.root.attrib["name"]+"</h3>")
            obj = mod
            out.write(obj.handle_contents(obj.root, False))
            out.write("</div>")

            
###############################################
#           Start main
###############################################
if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Args: " + str(len(sys.argv)))
        #        0       1          2          3          4          5       6
        print("Usage: <js-file> <css-file> <xsl-file> <out-file   <in-1> [<in-2> [...]]")
        sys.exit(0)

    jsfile=sys.argv[1]
    cssfile=sys.argv[2]
    xslfile=sys.argv[3]
    outfile=sys.argv[4]



    with open(jsfile, "r") as in_handle:
        js = in_handle.read()

    with open(cssfile, "r") as in_handle:
        css = in_handle.read()

    with open(xslfile, "rb") as in_handle:
        xslb64 = base64.b64encode(in_handle.read()).decode('ascii')

    # Technical Decisions
    tds={}

    #- Run through the rest of the inputs
    for inIndex in range(5, len(sys.argv)):
        root = ET.parse(sys.argv[inIndex]).getroot()
        bases = root.findall( ".//cc:base-pp", PPObject.ns)
        
        if len( bases ) > 0:
            PPMap.add_mod(PPObject.PP(root), bases)
        elif root.tag == PPObject.cc("PP"):
            ppmap = PPMap.get_pp_map(root.attrib["name"])    # Get any existing one
            ppmap.base= PPObject.PP(root)
        elif root.tag == PPObject.cc("technical-decisions"): # If it's a TD
            tds[sys.argv[inIndex]]=root                      # save it for the end

    for tdpath in tds:
        td=tds[tdpath]
        appliedTD=False
        for bunch in td.findall(".//cc:bunch", PPObject.ns):
            for applies in bunch.findall("./cc:applies-to", PPObject.ns):
                name=applies.attrib["name"]
                maxver=float(applies.attrib["max-inclusive"])
                if name in PPMap.basenameToDefs:
                    ppobj=PPMap.basenameToDefs[name].base
                    if maxver >= ppobj.getVersion(): ppobj.applyBunchOfTDs(bunch)
                elif name in PPMap.modnameToDef:
                    module=PPMap.modulenameToDef[name].applyBunchOfTDs(bunch)
                else: 
                    print("Could not find PP or PP-Mod with the name: " + name +". Ignoring.");
                print("Applying bunch to " + name + " " + applies.attrib["max-inclusive"])

    with open(outfile, "w") as out:
        out.write(
"""<html xmlns='http://www.w3.org/1999/xhtml'>
   <head>\n
      <meta charset='utf-8'></meta>\n
      <title>Protection Profile Security Target Generator</title>\n
      <style type='text/css'>
""")
        out.write(css)
        out.write("""      </style>
           <script type='text/javascript'>//<![CDATA[
""")
        # out.write(" const ORIG64='"+inb64+"';\n")
        # out.write(" const XSL64='"+xslb64+"';\n")
        out.write(js)
        PPMap.write_init_pp_structures(out)
        out.write( """
//]]>
       </script>
    </head>
    <body onkeypress='handleKey(event); return true;' onload='init();'>
      <div id='fade-pane'>
        Press <i>Control+'?'</i> (aka <i>Control+Shift+'/'</i> for help.
      </div>
      <div id='help-pane'>
        Future Help Goes Here.
      </div>
      <div class="basepane">
      <h1>Security Target Wizard</h1>
      <div class='warning-pane'>
        <noscript><h2 class="warning">This page requires JavaScript.</h2></noscript>
           <h2 class="warning" id='url-warning' style="display: none;">
             Most browsers do not store cookies from local pages (i.e, 'file:///...').
             When you close this page, all data will most likely be lost.</h2>
      </div>
     
    """)
        PPMap.build_worksheet(out)
        # Make sure a base is selected to show the buttons
        out.write("<div class='")
        for base in PPMap.basenameToDefs:
            out.write("dep:"+PPObject.to_id(base)+" ")
        out.write( """'>
         <button type="button" onclick="generateReport()">XML Record</button>
         <button type="button" onclick="fullReport()">HTML Report</button>
       </div>
       </div>
       <div id='report-node' style="display: none;"/>
    </body>
</html>
""")
    sys.exit(0)

 
    # state.makeSelectionMap()
    # out.write( state.handle_contents(state.root, False)

