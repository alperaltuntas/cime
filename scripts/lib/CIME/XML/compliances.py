"""
Common interface to XML files which follow the comply format.
This class inherits from the abstract class GenericXML.
"""

from CIME.XML.standard_module_setup import *
from CIME.XML.files import Files
from CIME.XML.generic_xml import GenericXML

logger = logging.getLogger(__name__)

class Compliances(GenericXML):

    def __init__(self, infile=None, files=None):
        if files is None:
            files = Files()
        if infile is None:
            infile = files.get_value("COMPLY_SPEC_FILE")
        logger.debug("Compliances specification files is {}".format(infile))
        schema = files.get_schema("COMPLY_SPEC_FILE")
        GenericXML.__init__(self,infile,schema)
        #try:
        #    GenericXML.__init__(self,infile,schema)
        #except:
        #    expect(False, "Could not initialize Grids")
        self._version = self.get_version()

        print("Constructed Comply.")

