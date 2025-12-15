import cpp

bindingset[m]
string getFullSignature(Function m) {
    result = m.getType().getName() + " " + 
    m.getName() + "(" + 
    concat(int i | i = [0 .. m.getNumberOfParameters()] | m.getParameter(i).getType().getName() + " " +
        "p" + i, ", " order by i asc) + ")"
}

string getInternalSignature(Function m) {
    result = m.getName() + "(" + 
    concat(int i | i = [0 .. m.getNumberOfParameters()] | m.getParameter(i).getType().getName(), ", " order by i asc) + ")"
}

bindingset[m]
string paramTypes(Function m) {
  if m.getNumberOfParameters() = 0
    then
        result = ""
    else
    result = concat(int i | i = [0 .. m.getNumberOfParameters()] | m.getParameter(i).getType().getName(), ";" order by i asc)
}



predicate isTested(Function m) {
    exists(Function c |
        c = m and
        c.getLocation().toString().matches("%/test%")
    )
}

from
    Function c
where
  c.getFile().fromSource() and
  c.getName() != "" and
  c.getDefinition().toString() != "" and
  not c.getLocation().toString().matches("file:///usr/%")
  and not c.getLocation().toString().matches("file://:0:0:%")
  // and not isTested(c)
select
    "None" as package,
    "None" as clazz,
    c.getName() as func,
    getFullSignature(c) as full_signature,
    getInternalSignature(c) as internal_signature,
    c.getLocation().toString() as location,
    paramTypes(c) as parameter_types,
    c.getType().getName() as return_type,
    "None" as doc
