-- Presentation only: never returns a deadline for the actual firing slot.
local M={}
function M.compute(view,now)
 local remaining=view.next and math.max(0,(view.next-now)/1000000)or 0
 local period=math.max(0.000001,view.interval/1000000)
 local seconds=math.ceil(remaining)
 return {count=view.charges,recharging=remaining>0,remaining=remaining,
  progress=remaining>0 and math.max(0,math.min(1,1-remaining/period))or 1,
  minutes=math.floor(seconds/60),seconds=seconds%60,available=view.charges>0}
end
return M
