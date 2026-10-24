-- A single private poller that preserves the BSL update callback and returns.
local M={}
function M.attach(watch)
 local prior=rawget(_G,'update');local callback
 local function after(...)
  if watch.status=='running' then
   local ok,why=pcall(watch.tick)
   if not ok and type(why)=='table' and why.reason=='OPS read budget exhausted' then
    return ...
   elseif not ok then
    local cleaned,cleanup=pcall(watch.cancel)
    watch.status='rejected'
    print('[O.P.S.扩展改装件] update rejected: '..tostring(why))
    pcall(function()
     local log=assert(CowboyBingusModLoader.open_log('OpsStandaloneError.log'))
     log:write(tostring(why)..'\n'..(cleaned and ''or tostring(cleanup)..'\n'));log:flush();log:close()
    end)
   end
  end
  if watch.status~='running' and update==callback then update=prior end
  return ...
 end
 callback=function(...)
  if prior then return after(prior(...))end
  return after()
 end
 update=callback
 return watch
end
return M
