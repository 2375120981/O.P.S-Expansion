local config = require('mods/c09nat/ops_cooldown_40s/config')
local ok,result=pcall(function()
    return require('mods/c09nat/ops_cooldown_40s/data_timing').start(config)
end)
if not ok then
    print('[O.P.S.扩展改装件] Initialization refused: '..tostring(result))
    pcall(function()
        local log=assert(CowboyBingusModLoader.open_log('OpsTimingError.log'))
        log:write(tostring(result)..'\n');log:flush();log:close()
    end)
end
return ok and result or {status='rejected',error=tostring(result)}
