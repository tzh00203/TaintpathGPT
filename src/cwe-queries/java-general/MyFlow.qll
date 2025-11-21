import java
import semmle.code.java.dataflow.DataFlow
import semmle.code.java.frameworks.javaee.ejb.EJBRestrictions
private import semmle.code.java.dataflow.FlowSources
private import semmle.code.java.dataflow.ExternalFlow

import MySources
import MySinks
import MySummaries

module MyTaintFlowConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node src) {
    isGPTDetectedSource(src)
  }

  predicate isSink(DataFlow::Node snk) {
    isGPTDetectedSink(snk)
  }

  predicate isAdditionalFlowStep(DataFlow::Node pre, DataFlow::Node next) {
    isGPTDetectedStep(pre, next)
  }
}

/** Tracks flow of unvalidated user input that is used in Runtime.Exec */
module MyTaintFlow = TaintTracking::Global<MyTaintFlowConfig>;
