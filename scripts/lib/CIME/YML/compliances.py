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

# Assertions in config_comply.yaml files are interpreted as implications. For example
#       expr1:
#           assert expr2, errMsg
# is interpreted as (expr1 -> expr2), where expr1 is the antecedent expr2 is the consequent,
# and errMsg is the message to be printed if the implication evaluates to False.
Implication = namedtuple('Implication', ['antecedents', 'consequent', 'errMsg', 'variables', 'full_expr'])

class Compliances(ParamGen):

    def __init__(self, data_dict, match='last'):
        self._implications = [] # i.e., relations
        self._var_impl_idx = {} # mapping from varname to set of implication id's involving var
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

    def implications(self, varname=None):
        if varname==None:
            return self._implications.copy()
        else:
            var_implications = []
            if varname in self._var_impl_idx:
                var_implications = [self._implications[idx] for idx in self._var_impl_idx[varname]]
            return var_implications

    def _add_implication(self, antecedents, consequent, errMsg):
        """adds an implication in the form of antecedents -> consequent."""
        cond_id = len(self._implications)
        full_expr = 'not({}) or {}'.format( ' and '.join(antecedents), consequent)
        logger.debug("Adding implication: {}".format(full_expr))
        impl_vars = get_expandable_vars(full_expr) # all variables involved in implication
        self._implications.append(Implication(antecedents, consequent, errMsg, impl_vars, full_expr))
        for var in impl_vars:
            if not var in self._var_impl_idx:
                self._var_impl_idx[var] = set()
                self._vars_related[var] = set()
            self._var_impl_idx[var].add(cond_id)
            for var_other in set(impl_vars) - {var}:
                self._vars_related[var].add(var_other)

    def unfold_implications(self):
        logger.info("Unfolding all implications...")
        def _unfold_implications_recursive(data, antecedents=[]):
            if isinstance(data, dict):

                for guard, val in data.items():
                    if isinstance(val, list):
                        for item in val:
                            _unfold_implications_recursive(item, antecedents+[guard])
                    elif ParamGen._is_guarded_dict(data):
                        _unfold_implications_recursive(val, antecedents+[guard])
                    else:
                        raise RuntimeError("Invalid Compliances DPD.")
            elif isinstance(data, str):
                consequent, errMsg = Compliances._split_assertion_expr(data)
                self._add_implication(antecedents, consequent, errMsg)
        _unfold_implications_recursive(self.data)

    @staticmethod
    def check_implication(implication, expand_func):
        logger.debug("Checking implication: {}".format(implication.full_expr))
        implication_relevant = True
        for antecedent in implication.antecedents:
            antecedent_expanded = ParamGen._expand_vars(antecedent, expand_func)
            antecedent_eval = eval_formula(antecedent_expanded)
            if antecedent_eval != True:
                implication_relevant = False
                break
        if implication_relevant:
            logger.debug("Implication is relevant.")
            consequent_expanded = ParamGen._expand_vars(implication.consequent, expand_func)
            logger.debug("Implication evaluation: {}".format(eval_formula(consequent_expanded)))
            assert eval_formula(consequent_expanded), implication.errMsg
        else:
            logger.debug("Implication is irrelevant.")



    def check_all(self, expand_func):
        assert callable(expand_func), "Must provide expand_func function"
        logger.info("Checking all implications in Compliances object.")
        for implication in self._implications:
            Compliances.check_implication(implication, expand_func)

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