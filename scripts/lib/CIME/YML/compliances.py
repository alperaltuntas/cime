"""
Common interface to XML files which follow the comply format.
This class inherits from the abstract class GenericXML.
"""

from CIME.XML.standard_module_setup import *
from CIME.XML.files import Files
from CIME.ParamGen.paramgen_utils import is_formula, get_expandable_vars
from CIME.ParamGen.paramgen_utils import eval_formula
from CIME.ParamGen.paramgen import ParamGen
from collections import namedtuple
import re

import logging
logger = logging.getLogger(__name__)

# Compliance expressions in config_comply.yaml files consist of a precondition and an assertion,
# where precondition is the key and the assertion is the value, e.g.,:
# precondition:
#   - assertion_1
#   - assertion_2
# where precondition is an arbitrary Python expression that evaluates to a boolean value and
# assertions are Python assertion expressions. Both the preconditon and the assertion can include
# literals and expandable parameters.
Assertion = namedtuple('Assertion', ['preconditions', 'expression', 'errMsg', 'variables'])

class Compliances(ParamGen):

    def __init__(self, data_dict, match='last'):
        self._assertions = [] # i.e., compliances
        self._var_assertions_idx = {} # mapping from varname to set of assertions id's involving var
        self._vars_related = {}

        ParamGen.__init__(self, data_dict, match)
        logger.info("Compliances object created.")

    @classmethod
    def from_cime(cls, infile=None, files=None, match='last'):
        logger.info("Creating compliances object from CIME config_compliances.yaml...")
        if files is None:
            files = Files()
        if infile is None:
            infile = files.get_value("COMPLY_SPEC_FILE")
        return cls.from_yaml(infile)

    @staticmethod
    def _split_assertion_expr(assertion):
        """splits an assertion expression into its two parts: (1) logical assertion and (2) associated error message."""
        assert "assert" in assertion
        errMsgTemp = re.findall('(,\s*"[^"]*"$|,\s*\'[^\']*\'$)',assertion)
        assert len(errMsgTemp)==1, "Cannot parse assertion "+assertion
        errMsgTemp = errMsgTemp[0]
        errMsg = errMsgTemp[1:].strip()
        expr = assertion\
                .replace(errMsgTemp,'')\
                .replace('assert','',1).strip()
        return expr, errMsg

    def assertions(self, varname=None):
        if varname==None:
            return self._assertions.copy()
        else:
            var_assertions = []
            if varname in self._var_assertions_idx:
                var_assertions = [self._assertions[idx] for idx in self._var_assertions_idx[varname]]
            return var_assertions

    def _add_assertion(self, preconditions, expression, errMsg):
        """adds an assertion."""
        assertion_idx = len(self._assertions)
        preconditions_joined = ' and '.join(preconditions),
        logger.debug("Adding assertion: {}: {}".format(preconditions_joined, expression))
        preconditions_vars = get_expandable_vars(expression) # variables mentioned in preconditions
        expression_vars = get_expandable_vars(expression) # variables mentioned in assertion
        all_vars = preconditions_vars | expression_vars
        self._assertions.append(Assertion(preconditions, expression, errMsg, all_vars))
        for var in expression_vars:
            if not var in self._var_assertions_idx:
                self._var_assertions_idx[var] = set()
                self._vars_related[var] = set()
            self._var_assertions_idx[var].add(assertion_idx)
            for var_other in set(expression_vars) - {var}:
                self._vars_related[var].add(var_other)

    def unfold_compliances(self):
        logger.info("Unfolding all compliance rules...")
        def _unfold_compliances_recursive(data, preconditions=[]):
            if isinstance(data, dict):

                for guard, val in data.items():
                    if isinstance(val, list):
                        for item in val:
                            _unfold_compliances_recursive(item, preconditions+[str(guard)])
                    elif ParamGen._is_guarded_dict(data):
                        _unfold_compliances_recursive(val, preconditions+[str(guard)])
                    else:
                        raise RuntimeError("Invalid Compliances DPD.")
            elif isinstance(data, str):
                expression, errMsg = Compliances._split_assertion_expr(data)
                self._add_assertion(preconditions, expression, errMsg)
        _unfold_compliances_recursive(self.data)

    @staticmethod
    def check_assertion(assertion, expand_func, expand_func_opt):
        logger.debug("Checking assertion: {}".format(assertion.expression))
        assertion_relevant = True
        for precondition in assertion.preconditions:
            precondition_expanded = ParamGen._expand_vars(precondition, expand_func)
            if "None" in precondition_expanded:
                logger.debug("Assertion precondition includes 'None' value(s), i.e., uninitialized vars. Skipping evaluation...")
                assertion_relevant = False
                break
            precondition_eval = eval_formula(precondition_expanded)
            if precondition_eval != True:
                assertion_relevant = False
                break
        if assertion_relevant:
            logger.debug("Assertion is relevant.")
            expression_expanded = ParamGen._expand_vars(assertion.expression, expand_func_opt)
            if "None" in expression_expanded:
                logger.debug("Assertion expression includes 'None' value(s), i.e., uninitialized vars. Skipping evaluation...")
                return
            logger.debug("Expression expanded: {}".format(expression_expanded))
            result = eval_formula(expression_expanded)
            logger.debug("Assertion evaluation: {}".format(result))
            assert result, assertion.errMsg
        else:
            logger.debug("Assertion is irrelevant.")



    def check_all(self, expand_func):
        assert callable(expand_func), "Must provide expand_func function"
        logger.info("Checking all assertions in Compliances object.")
        for assertion in self._assertions:
            Compliances.check_assertion(assertion, expand_func)

'''
    def gen_dependency_graph(self):
        try:
            import graphviz
        except:
            raise ImportError("Cannot import graphviz library required to generate dependency graphs")

        dot = graphviz.Digraph(comment='CIME XML var dependency')
        relations = self.get_children()
        for relation in relations:
            relate_vars = self.get(relation,"vars").split('~')
            for rvar in relate_vars:
                dot.node(rvar)
            for rvar1, rvar2 in zip(relate_vars[:-1], relate_vars[1:]):
                dot.edge(rvar1,rvar2)

        dot.render(format='png')
        print("Dependency graph generated.")


    def check(self, case):

        def get_xml_val(xml_var, relation):
            val = case.get_value(xml_var)
            expect(val!=None, "Cannot find XML case var "+xml_var+" specified in"
                            "config_compliances within the vars attributes of "+
                            self.get(relation,"id")+" relation.")
            return str(val)

        print("-------------Checking compliances------------")
        relations = self.get_children()

        for relation in relations:
            # relate_vars: xml case vars to be checked for relational integrity
            relate_vars = self.get(relation,"vars").split('~')
            assert len(relate_vars)>=2, "The following relation has less than two xml variables (to be split by ~):"+relate_vars

            assertions = self.get_children("assert",root=relation)
            for assertion in assertions:
                instance = self.text(assertion)
                instance_vals = instance.split('~')
                assert len(relate_vars)==len(instance_vals), "Wrong number of arguments in assertion "+assertion

                instance_relevant = True
                for i in range(len(relate_vars)-1):
                    relate_val = get_xml_val(relate_vars[i],relation)
                    if not re.search(instance_vals[i],relate_val):
                        instance_relevant = False
                        break
                if instance_relevant:
                    errMsg = self.get(assertion,"errMsg")
                    relate_val = get_xml_val(relate_vars[-1],relation)
                    expect(re.search(instance_vals[-1],relate_val),errMsg)

            rejections = self.get_children("reject",root=relation)
            for rejection in rejections:
                instance = self.text(rejection)
                instance_vals = instance.split('~')
                assert len(relate_vars)==len(instance_vals), "Wrong number of arguments in rejection "+rejection

                instance_relevant = True
                for i in range(len(relate_vars)-1):
                    relate_val = get_xml_val(relate_vars[i],relation)
                    if not re.search(instance_vals[i],relate_val):
                        instance_relevant = False
                        break
                if instance_relevant:
                    errMsg = self.get(rejection,"errMsg")
                    relate_val = get_xml_val(relate_vars[-1],relation)
                    expect(not re.search(instance_vals[-1],relate_val),errMsg)

        print("done. no compliance violation.")
'''