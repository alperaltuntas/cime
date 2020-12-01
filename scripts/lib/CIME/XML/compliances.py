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
            relate_vars = self.get(relation,"vars").split('->')
            assert len(relate_vars)>=2, "The following relation has less than two xml variables (to be split by ->):"+relate_vars

            relate_vals = [] # the XML case
            for relate_var in relate_vars:
                relate_val = case.get_value(relate_var)
                expect(relate_val!=None, "Cannot find XML case var "
                    +relate_var+" specified in config_compliances as the "
                    "relate attribute of "+self.get(relation,"id")+" relation.")
                relate_vals.append(relate_val)

            assertions = self.get_children("assert",root=relation)
            for assertion in assertions:
                instance = self.get(assertion,"inst")
                instance_vals = instance.split('->')
                assert len(relate_vars)==len(instance_vals), "Wrong number of arguments in assertion "+assertion

                instance_relevant = True
                for i in range(len(relate_vars)-1):
                    if not re.search(instance_vals[i],relate_vals[i]):
                        instance_relevant = False
                        break
                if instance_relevant:
                    errMsg = self.get(assertion,"errMsg")
                    expect(re.search(instance_vals[-1],relate_vals[-1]),errMsg)

            rejections = self.get_children("reject",root=relation)
            for rejection in rejections:
                instance = self.get(rejection,"inst")
                instance_vals = instance.split('->')
                assert len(relate_vars)==len(instance_vals), "Wrong number of arguments in rejection "+rejection

                instance_relevant = True
                for i in range(len(relate_vars)-1):
                    if not re.search(instance_vals[i],relate_vals[i]):
                        instance_relevant = False
                        break
                if instance_relevant:
                    errMsg = self.get(rejection,"errMsg")
                    expect(not re.search(instance_vals[-1],relate_vals[-1]),errMsg)
