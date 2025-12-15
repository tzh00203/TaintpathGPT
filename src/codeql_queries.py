QL_SOURCE_PREDICATE = """\
import java
import semmle.code.java.dataflow.DataFlow
private import semmle.code.java.dataflow.ExternalFlow

predicate isGPTDetectedSource(DataFlow::Node src) {{
{body}
}}

{additional}
"""

QL_SOURCE_PREDICATE_CPP = """\
import cpp
import semmle.code.cpp.ir.dataflow.DataFlow
import semmle.code.cpp.ir.dataflow.TaintTracking

predicate isGPTDetectedSource(DataFlow::Node src) {{
{body}
}}

{additional}
"""

QL_SOURCE_PREDICATE_PYTHON = """\
import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking

predicate isGPTDetectedSource(DataFlow::Node src) {{
{body}
}}

{additional}
"""


QL_SINK_PREDICATE = """\
import java
import semmle.code.java.dataflow.DataFlow
private import semmle.code.java.dataflow.ExternalFlow

predicate isGPTDetectedSink(DataFlow::Node snk) {{
{body}
}}

{additional}
"""

QL_SINK_PREDICATE_CPP = """\
import cpp
import semmle.code.cpp.ir.dataflow.DataFlow
import semmle.code.cpp.ir.dataflow.TaintTracking

predicate isGPTDetectedSink(DataFlow::Node snk) {{
{body}
}}

{additional}
"""

QL_SINK_PREDICATE_PYTHON = """\
import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking

predicate isGPTDetectedSink(DataFlow::Node snk) {{
{body}
}}

{additional}
"""

QL_SUBSET_PREDICATE = """\
predicate isGPTDetected{kind}Part{part_id}(DataFlow::Node {node}) {{
{body}
}}
"""

CALL_QL_SUBSET_PREDICATE = "    isGPTDetected{kind}Part{part_id}({node})"

QL_STEP_PREDICATE = """\
import java
import semmle.code.java.dataflow.DataFlow
private import semmle.code.java.dataflow.ExternalFlow

predicate isGPTDetectedStep(DataFlow::Node prev, DataFlow::Node next) {{
{body}
}}
"""

QL_STEP_PREDICATE_CPP = """\
import cpp
import semmle.code.cpp.ir.dataflow.DataFlow
import semmle.code.cpp.ir.dataflow.TaintTracking

predicate isGPTDetectedStep(DataFlow::Node prev, DataFlow::Node next) {{
{body}
}}
"""

QL_STEP_PREDICATE_PYTHON = """\
import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking

predicate isGPTDetectedStep(DataFlow::Node pre, DataFlow::Node next) {{
{body}
}}
"""

QL_METHOD_CALL_SOURCE_BODY_ENTRY = """\
    (
        src.asExpr().(Call).getCallee().getName() = "{method}" and
        src.asExpr().(Call).getCallee().getDeclaringType().getSourceDeclaration().hasQualifiedName("{package}", "{clazz}")
    )\
"""

QL_METHOD_CALL_SOURCE_BODY_ENTRY_CPP = """\
    (
       src.asExpr().(Call).getTarget().hasName("{method}")
    )\
"""

QL_METHOD_CALL_SOURCE_BODY_ENTRY_PYTHON = """\
    exists(Call c, Attribute attr |
        attr = c.getFunc() and
        (
            attr.getObject().toString() = "{package}" or
            attr.getObject().toString() = "{clazz}"
        )
        and
        attr.getAttr() = "{method}" and
        src.asExpr() = c
  )\
"""

QL_FUNC_PARAM_SOURCE_ENTRY = """\
    exists(Parameter p |
        src.asParameter() = p and
        p.getCallable().getName() = "{method}" and
        p.getCallable().getDeclaringType().getSourceDeclaration().hasQualifiedName("{package}", "{clazz}") and
        ({params})
    )\
"""

QL_FUNC_PARAM_SOURCE_ENTRY_CPP_PART1 = """\
     (
       src.asExpr().(Call).getTarget().hasName("{method}")
    )\
"""

QL_FUNC_PARAM_SOURCE_ENTRY_CPP_PART2 = """\
    exists(Function c |
        c.hasName("{method}") and
        src.asParameter() = c.getAParameter()
  )\
"""

QL_FUNC_PARAM_SOURCE_ENTRY_PYTHON = """\
    exists(Function func |
      func.toString() = "Function {method}" and
      ({params}) and
      (
        func.getScope().toString() = "Module {package}" or func.getScope().toString() = "Class {clazz}" or
        func.getScope().toString() = "Moudle {package}.{clazz}" or
        func.getEnclosingModule().toString() = "Module {package}.{clazz}" or
        "{package}.{clazz}".matches("%"+func.getEnclosingModule().getName())
      ) and
      (src.asExpr() = func.getAnArg() )
  )\
"""

# QL_FUNC_PARAM_SOURCE_ENTRY_KWARGS_PYTHON = """\
#     exists(Call call, Attribute attr, Function f |
#         call.getFunc() = attr and
#         attr.getAttr() = "{method}" and
#         (attr.getObject().toString() = "{class}" 
#         or attr.getObject().toString() = "{package}"
#         or attr.getObject().toString() = "Attribute")
#         and
#         call.getKwargs() = pre.asExpr() and
#         f.getName() = "{method}" and
#         f.getKwarg() = next.asExpr()
#       )\
# """

QL_FUNC_PARAM_NAME_ENTRY = """ p.getName() = "{arg_name}" """
QL_FUNC_PARAM_NAME_ENTRY_PYTHON = """ func.getAnArg().getName() = "{arg_name}" """

QL_SUMMARY_BODY_ENTRY = """\
    exists(Call c |
        (c.getArgument(_) = prev.asExpr() or c.getQualifier() = prev.asExpr())
        and c.getCallee().getDeclaringType().hasQualifiedName("{package}", "{clazz}")
        and c.getCallee().getName() = "{method}"
        and c = next.asExpr()
    )\
"""

QL_SUMMARY_BODY_ENTRY_CPP = """\
    exists(Call c |
        (
            c.toString() = "call to {method}" and
            c.getAnArgument() = prev.asExpr() and
            c.getAnArgument() = next.asExpr()
        )
    )\
"""

QL_SUMMARY_BODY_ENTRY_PYTHON = """\
  exists( Attribute attr, Call c, Function f |
    c.getFunc() = attr and
    attr.getAttr() = "{method}"  and
    c.getAnArg() = pre.asExpr() and
    attr.getAttr().toString() = f.getName() and
    f.getAnArg() = next.asExpr()
  )
  or
  exists( Call c |
     c.getFunc().toString() = "{method}" and
     c.getAnArg() = pre.asExpr() and 
     c = next.asExpr()
   )\
"""

QL_SUMMARY_BODY_ENTRY_PYTHON_KWARG = """
    exists(Call call, Attribute attr, Function f |
        call.getFunc() = attr and
        attr.getAttr() = "{method}" and
        call.getKwargs() = pre.asExpr() and
        f.getName() = "{method}" and
        f.getKwarg() = next.asExpr()
    )\
"""

QL_SINK_BODY_ENTRY = """\
    exists(Call c |
        c.getCallee().getName() = "{method}" and
        c.getCallee().getDeclaringType().getSourceDeclaration().hasQualifiedName("{package}", "{clazz}") and
        ({args})
    )\
"""

QL_SINK_BODY_ENTRY_CPP = """\
    exists(Call c|
      c.toString() = "call to {method}" and
      snk.asExpr() = c.getAnArgument()
  )\
"""

QL_SINK_BODY_ENTRY_PYTHON_KIND1 = """\
    exists(Call c, Attribute attr |
        attr = c.getFunc() and
        attr.getAttr() = "{method}" and
        attr.getObject().toString() = "{package}" and
        ({args})
    )\
"""

QL_SINK_BODY_ENTRY_PYTHON_KIND2 = """\
    exists(Call c |
        c.getFunc().toString() = "{method}" and
        ({args})
    )\
"""

QL_SINK_ARG_NAME_ENTRY = """ c.getArgument({arg_id}) = snk.asExpr().(Argument) """
QL_SINK_ARG_NAME_ENTRY_PYTHON = """ c.getAnArg() = snk.asExpr()  """


QL_SINK_ARG_THIS_ENTRY = """ c.getQualifier() = snk.asExpr() """
QL_SINK_ARG_THIS_ENTRY_PYTHON = """ attr.getObject() = snk.asExpr() and  """

QL_BODY_OR_SEPARATOR = "\n    or\n"

EXTENSION_YML_TEMPLATE = """\
extensions:
  - addsTo:
      pack: codeql/java-all
      extensible: sinkModel
    data:
{sinks}
  - addsTo:
      pack: codeql/java-all
      extensible: sourceModel
    data:
{sources}
"""

EXTENSION_YML_TEMPLATE_PYTHON = """\
extensions:
  - addsTo:
      pack: codeql/python-all
      extensible: sinkModel
    data:
{sinks}
  - addsTo:
      pack: codeql/python-all
      extensible: sourceModel
    data:
{sources}
"""

EXTENSION_SRC_SINK_YML_ENTRY = """\
      - ["{package}", "{clazz}", True, "{method}", "", "", "{access}", "{tag}", "manual"]\
"""

EXTENSION_SUMMARY_YML_ENTRY = """\
      - ["{package}", "{clazz}", True, "{method}", "", "", "{access_in}", "{access_out}", "{tag}", "manual"]\
"""
