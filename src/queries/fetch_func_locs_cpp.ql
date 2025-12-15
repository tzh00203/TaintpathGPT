import cpp
from
  Function c
where
  c.getFile().fromSource() and
  c.getName() != "" and
  c.getDefinition().toString() != "" and
  not c.getLocation().toString().matches("file:///usr/%")
  and not c.getLocation().toString().matches("file://:0:0:%")
select
  c.getName() as name,
  c.getFile().getRelativePath() as file,
  c.getLocation().getStartLine() as start_line,
  c.getLocation().getEndLine() as end_line