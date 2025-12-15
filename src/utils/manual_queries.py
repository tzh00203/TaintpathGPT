QL_SUMMARY_BODY_ENTRY_MANUAL_PYTHON = """\
  exists(Call joinCall |
     joinCall.getFunc().toString() = "join" and
     joinCall.getAnArg() = prev.asExpr() and
       joinCall = next.asExpr()
   )
  or
  exists(List list |
     list.getAnElt() = prev.asExpr() and
     list = next.asExpr() 
  )
  or
  exists(BinaryExpr binExpr |
     binExpr.getOp().toString() in ["Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow"] and
     (
       binExpr.getLeft() = prev.asExpr() or
       binExpr.getRight() = prev.asExpr()
     ) and
     binExpr = next.asExpr()
   )
   or
   exists(Attribute attr |
      attr.getObject() = prev.asExpr() and
      attr = next.asExpr()
   )\
"""

QL_SUMMARY_BODY_ENTRY_MANUAL_CPP = """
   exists(FieldAccess fa |
      (next.asExpr() = fa or
      next.asIndirectExpr() = fa)
      and
      (prev.asIndirectExpr() = fa.getQualifier() or prev.asExpr() = fa.getQualifier())
    )
"""