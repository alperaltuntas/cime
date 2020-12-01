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

    def gen_dependency_graph(self):
        try:
            import graphviz
        except:
            raise ImportError("Cannot import graphviz library required to generate dependency graphs")

        dot = graphviz.Digraph(comment='CIME XML var dependency')
        relations = self.get_children()
        for relation in relations:
            relate_vars = self.get(relation,"relate").split('->')
            for rvar in relate_vars:
                dot.node(rvar)
            for rvar1, rvar2 in zip(relate_vars[:-1], relate_vars[1:]):
                dot.edge(rvar1,rvar2)

        dot.render(format='png')
        print("Dependency graph generated.")


    def check(self, case):

        print("-------------Checking compliances------------")
        print(self.get_id())
        relations = self.get_children()

        for relation in relations:
            # relate_vars: xml case vars to be checked for relational integrity
            relate_vars = self.get(relation,"relate").split('->')
            arity = int(self.get(relation,"arity"))
            assert arity == len(relate_vars), "Wrong arity in relation "+self.get(relation,"id")

            relate_vals = [] # the XML case
            for relate_var in relate_vars:
                relate_val = case.get_value(relate_var)
                expect(relate_val!=None, "Cannot find XML case var "
                    +relate_var+" specified in config_compliances as the "
                    "relate attribute of "+self.get(relation,"id")+" relation.")
                relate_vals.append(relate_val)

            entries = self.get_children("entry",root=relation)
            for entry in entries:
                entry_id = self.get(entry,"id")
                assertions = self.get_children("assert",root=entry)
                rejections = self.get_children("reject",root=entry)
                print(entry_id, relate_vals[0])
                if re.search(entry_id, relate_vals[0]):
                    if arity==2:
                        for assertion in assertions:
                            val = self.text(assertion)
                            errMsg = self.get(assertion,"errMsg")
                            expect(re.search(val, relate_val),errMsg)
                        for rejection in rejections:
                            val = self.text(rejection)
                            errMsg = self.get(rejection,"errMsg")
                            expect(not re.search(val, relate_val),errMsg)
                    else:
                        raise NotImplementedError

