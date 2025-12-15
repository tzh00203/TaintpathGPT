import cpp

string getCallStr(Call c){
  result = c.getTarget().getName() + "(...)"
}
string getFullSignature(Call m) {
    result = m.getType().getName() + " " + 
    m.getTarget().toString() + "(" + 
    concat(int i | i = [0 .. m.getNumberOfArguments()] | m.getArgument(i).getType().getName() + " " +
        "p" + i, ", " order by i asc) + ")"
}

string getInternalSignature(Call m) {
    result = m.getTarget().toString() + "(" + 
    concat(int i | i = [0 .. m.getNumberOfArguments()] | m.getArgument(i).getType().getName(), ", " order by i asc) + ")"
}

bindingset[m]
string paramTypes(Call m) {
    result = concat(int i | i = [0 .. m.getNumberOfArguments()] | m.getArgument(i).getType().getName(), ";" order by i asc)
}


from Call api
where not api.getLocation().toString().matches("file:///usr/%")
and not api.getLocation().toString().matches("file://:0:0:%")
// select f.getTarget().getName(),  getFullSignature(f), getInternalSignature(f),f.getTarget().getName(),f.getLocation()
select
    getCallStr(api) as callstr,
    "None" as package,
    "None" as clazz,
    getFullSignature(api) as full_signature,
    getInternalSignature(api) as internal_signature,
    api.getTarget().getName() as func,
    "true" as is_static,
    api.getFile() as file,
    api.getLocation().toString() as location,
    paramTypes(api) as parameter_types,
    api.getType().getName() as return_type,
    "None" as doc