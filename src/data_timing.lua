-- Experimental data-only approach: no executable memory writes or native hooks.
local M={}
function M.start(options)
    options=options or {}
    local r=require('mods/c09nat/ops_cooldown_40s/standalone_runtime').create()
    local b=require('mods/c09nat/ops_cooldown_40s/local_bytes')
    local p=require('mods/c09nat/ops_cooldown_40s/local_schema')
    local module=assert(r.module('game.dll'))
    assert(r.module_hash(module)==p.dll_sha,'unsupported game.dll')
    assert(r.module_hash(assert(r.module('helldivers2.exe')))==p.exe_sha,'unsupported executable')
    local base=r.address(module)
    local loader=assert(rawget(_G,'CowboyBingusModLoader'))
    local log=assert(loader.open_log('OpsDataTiming.log'))
    local function emit(s)log:write(s..'\n');log:flush()end
    local function ptr(at)
        local s=r.read(at,8);if not s then return end
        local high=b.u32(s,4);if high>32767 then return end
        local n=b.u32(s,0)+high*4294967296
        if n>=65536 then return n end
    end
    local function time(s,o)
        local high=b.u32(s,o+4);if high>2097151 then return end
        return b.u32(s,o)+high*4294967296
    end
    local function encode64(n)
        return b.encode(n%4294967296,'u32')..b.encode(math.floor(n/4294967296),'u32')
    end
    local function store(at,expected,value)
        assert(r.read(at,#expected)==expected,'data changed before write')
        local region=assert(r.query(at),'data region unavailable')
        assert(region.state==0x1000 and (region.protect==2 or region.protect==4 or region.protect==8),
            'target is not a supported data region')
        assert(at+#value<=region.base+region.size,'data write crosses region')
        local page=at-at%4096
        assert(at+#value<=page+4096,'data write crosses page')
        local old
        if region.protect==2 then old=assert(r.protect(page,4096,4),'data protection failed')end
        local ok,why=pcall(function()assert(r.write(at,value),'data write failed')end)
        if old then assert(r.protect(page,4096,old),'data protection restoration failed')end
        assert(ok,why)
        assert(r.read(at,#value)==value,'data write verification failed')
    end
    local originals={};local cooldowns={};local seen={};local watch={status='running'}
    local function definition()
        local at=ptr(base+p.stratagem.table_rva+118*8)
        local s=at and r.read(at,400)
        if s and b.u32(s,0)==118 and b.u32(s,4)==3523620028 then return at,s end
    end
    local storage
    local hud
    if options.storage then
        storage=require('mods/c09nat/ops_cooldown_40s/storage').new({reader=r,bytes=b,
            store=store,encode64=encode64,emit=emit,definition=definition})
    end
    if options.storage and options.native_hud then
        local ok,result=pcall(function()
            return require('mods/c09nat/ops_cooldown_40s/hud_native').new({reader=r,
                bytes=b,base=base,store=store,emit=emit})
        end)
        if ok then hud=result else emit('HUD_DISABLED '..tostring(result))end
    end
    local last_metrics=0;local peak_reads=0;local peak_queries=0
    function watch.tick()
        if r.stats then
            local reads,queries=r.stats()
            peak_reads=math.max(peak_reads,reads);peak_queries=math.max(peak_queries,queries)
            local wall=r.monotonic_time()
            if wall-last_metrics>=60 then
                emit(string.format('PERF peak_read_bytes=%d peak_queries=%d limit_bytes=262144',peak_reads,peak_queries))
                last_metrics=wall;peak_reads=0;peak_queries=0
            end
        end
        if r.begin_budget then r.begin_budget()end
        local def,d=definition();if not def then return end
        if options.cooldown then
            assert(options.cooldown==40 or options.cooldown==70,'unsupported cooldown configuration')
            local current=d:sub(105,108);local target=b.encode(options.cooldown,'f32')
            if current==b.encode(80,'f32')then
                store(def+104,current,target);cooldowns[def]=current
                emit('BASE_COOLDOWN 80 -> '..options.cooldown)
            elseif current~=target then error('unexpected OPS cooldown; stopped')end
        end
        if storage then storage.prepare(def,d)end
        local wait=d:sub(85,88)
        if wait==b.encode(2,'f32') then
            store(def+84,wait,b.encode(0,'f32'));originals[def]=wait
            emit('BASE_WAIT 2 -> 0')
        elseif wait~=b.encode(0,'f32') then
            error('unexpected OPS base wait; stopped')
        end
        local manager=ptr(base+55037520);local clock=ptr(base+53633864)
        if not manager or not clock then return end
        local s=r.read(clock+24,8);local now=s and time(s,0)
        local countdata=r.read(manager+184832,4)
        local owners=countdata and b.u32(countdata,0)
        if not now or not owners or owners>32 then return end
        if storage then storage.begin(now)end
        for owner=0,owners-1 do
            local entry=manager+56+owner*5776
            local owner_key=r.read(manager+owner*5776,8)
            local count=r.read(entry+1928,4);local slots=count and b.u32(count,0)
            -- Incomplete reads must not make finish() discard existing charges.
            if not owner_key or not slots or slots>16 then return end
            if slots and slots<=16 then for slot=0,slots-1 do
                local at=entry+392+slot*48;local record=r.read(at,48)
                if not record then return end
                if record and b.u32(record,0)==118 then
                    local start,due=time(record,16),time(record,32)
                    if not start or not due or not time(record,24)then return end
                    local key=at
                    -- Ignore inactive/sentinel entries and only normalize a freshly
                    -- observed call. Deadline is anchored to start, never now+2.
                    if start and due and start>0 and start<=now and now-start<2000000
                        and due>now and seen[key]~=start then
                        local target=start+2000000
                        assert(r.read(manager+owner*5776,8)==owner_key,'owner identity changed')
                        assert(r.read(at,32)==record:sub(1,32),'slot identity changed')
                        store(at+32,record:sub(33,40),encode64(target))
                        seen[key]=start
                        emit(string.format('CALL owner=%d slot=%d old=%.6f new=2.000000',
                            owner,slot,(due-start)/1000000))
                    end
                    if storage and owner_key then
                        storage.slot(at,record,now,b.hex(owner_key),start,due,time(record,24),
                            {index=slot,owner_at=manager+owner*5776,owner_bytes=owner_key})
                    end
                end
            end end
        end
        if storage then storage.finish()end
        if hud then
            local ok,why=pcall(hud.tick,storage.views(),now)
            if not ok and why~=r.budget_exhausted then emit('HUD_DISABLED '..tostring(why));hud=nil end
        end
    end
    function watch.cancel()
        watch.status='cancelled'
        if storage then storage.cancel()end
        for at,original in pairs(originals)do
            if ptr(base+p.stratagem.table_rva+118*8)==at
                and r.read(at+84,4)==b.encode(0,'f32') then
                store(at+84,b.encode(0,'f32'),original)
            end
        end
        for at,original in pairs(cooldowns)do
            if ptr(base+p.stratagem.table_rva+118*8)==at and
                r.read(at+104,4)==b.encode(options.cooldown,'f32')then
                store(at+104,b.encode(options.cooldown,'f32'),original)
            end
        end
        emit('STOPPED');log:close()
    end
    emit('VERSION 1.2.3 BSL_ONLY base_wait=0 hud_deadline=start+2s storage='..tostring(options.storage==true)..' native_hud='..tostring(options.native_hud==true))
    require('mods/c09nat/ops_cooldown_40s/local_scheduler').attach(watch)
    return watch
end
return M
