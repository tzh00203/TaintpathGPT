QL_SUMMARY_BODY_ENTRY_MANUAL_PYTHON = """\
  exists(Call joinCall |
     joinCall.getFunc().toString() = "join" and
     joinCall.getAnArg() = pre.asExpr() and
       joinCall = next.asExpr()
   )
  or
  exists(List list |
     list.getAnElt() = pre.asExpr() and
     list = next.asExpr() 
  )
  or
  exists(BinaryExpr binExpr |
     binExpr.getOp().toString() in ["Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow"] and
     (
       binExpr.getLeft() = pre.asExpr() or
       binExpr.getRight() = pre.asExpr()
     ) and
     binExpr = next.asExpr()
   )
   or
   exists(Attribute attr |
      attr.getObject() = pre.asExpr() and
      attr = next.asExpr()
   )\
"""