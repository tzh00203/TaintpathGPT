import cpp

predicate isExternalCall(Function f) {
    not f.getDeclaringModule().getName().matches(".*(test|mock).*") and
    not f.getDeclaringModule().getName().matches(".*junit.*") and
    not f.getDeclaringModule().getName().matches(".*hamcrest.*")
}

bindingset[f]
string fullSignature(Function f) {
    result = f.getReturnType().getName() + " " + f.getName() + "(" + 
            concat(int i | i = [0 .. f.getNumberOfParameters()] | 
            f.getParameter(i).getType().getName() + " " + f.getParameter(i).getName(), ", " order by i asc) + ")"
}

bindingset[f]
string paramTypes(Function f) {
    result = concat(int i | i = [0 .. f.getNumberOfParameters()] | 
            f.getParameter(i).getType().getName(), ";" order by i asc)
}

string isStaticAsString(Function f) {
    if f.isStatic() then 
        result = "true"
    else 
        result = "false"
}

from
    Call api
where
    isExternalCall(api.getCallee()) and
    api.getCallee().getStringSignature() != "()" and
    api.getCallee().getDeclaringType().getSourceDeclaration().getName() != "Object"
select
    api as callstr,
    api.getCallee().getDeclaringType().getSourceDeclaration().getPackage() as package,
    api.getCallee().getDeclaringType().getSourceDeclaration() as clazz,
    fullSignature(api.getCallee()) as full_signature,
    api.getCallee().getStringSignature() as internal_signature,
    api.getCallee() as func,
    isStaticAsString(api.getCallee()) as is_static,
    api.getFile() as file,
    api.getLocation().toString() as location,
    paramTypes(api.getCallee()) as parameter_types,
    api.getCallee().getReturnType().getName() as return_type
