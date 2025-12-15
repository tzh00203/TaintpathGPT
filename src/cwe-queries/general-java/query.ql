/**
 * @name Generic Taint Flow Vulnerability
 * @description Detects security vulnerabilities where user-controlled data flows into sensitive sinks without proper validation
 * @kind path-problem
 * @problem.severity error
 * @security-severity 9.0
 * @precision high
 * @id python/generic-taint-flow
 * @tags security
 */
import java
import semmle.code.java.dataflow.DataFlow
import semmle.code.java.frameworks.javaee.ejb.EJBRestrictions
private import semmle.code.java.dataflow.FlowSources
private import semmle.code.java.dataflow.ExternalFlow
import MyFlow
import MyTaintFlow::PathGraph

from MyTaintFlow::PathNode source, MyTaintFlow::PathNode sink
where MyTaintFlow::flowPath(source, sink)
select sink, source, sink,
  "Taint flow vulnerability: user-controlled input '$@' flows into security-sensitive function '$@' without proper validation",
  source.getNode(), "user input", sink.getNode(), "sensitive sink"