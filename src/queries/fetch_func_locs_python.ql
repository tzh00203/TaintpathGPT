
import python

from Function func
where func.getName() != ""
select
  func.getName() as name,
  func.getLocation() as file,
  func.getLocation().getStartLine() as start_line,
  func.getLocation().getEndLine() as end_line