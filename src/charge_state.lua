-- Serial recharge: full on entry; consuming another charge never resets progress.
local M={}
function M.new()return {charges=3,interval=70000000,ready=0,last_start=0}end
function M.advance(s,now)
    while s.next and now>=s.next do
        s.charges=math.min(3,s.charges+1)
        if s.charges==3 then s.next=nil else s.next=s.next+s.interval end
    end
end
function M.fire(s,start,interval)
    M.advance(s,start)
    assert(s.charges>0,'shot observed with empty storage')
    s.charges=s.charges-1;s.last_start=start
    s.ready=0 -- no short reload: stored charges may be used consecutively
    if not s.next then s.interval=interval;s.next=start+interval end
end
function M.deadline(s)
    return s.charges>0 and s.ready or math.max(s.ready,assert(s.next))
end
return M
