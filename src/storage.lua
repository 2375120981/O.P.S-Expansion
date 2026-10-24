local M={}
function M.new(c)
    local b=c.bytes
    local state=require('mods/c09nat/ops_cooldown_40s/charge_state')
    local states={};local originals={};local last_now;local active={};local views={}
    local function begin(now)
        if last_now and now<last_now then states={}end
        last_now=now;active={};views={}
    end
    local function finish()
        for key in pairs(states)do if not active[key]then states[key]=nil end end
    end
    local function prepare(def,d)
        local count=d:sub(81,84)
        if count==b.encode(4294967295,'u32') then
            c.store(def+80,count,b.encode(3,'u32'));originals[def]=count
            c.emit('STORAGE_CAPACITY 3')
        elseif count~=b.encode(3,'u32') then error('unexpected OPS use count')end
    end
    local function slot(at,record,now,owner_key,start,due,reuse,metadata)
        local key=owner_key..':'..string.format('%.0f',at)
        active[key]=true
        local s=states[key]
        if not s then s=state.new();states[key]=s;c.emit('STORAGE_INITIAL 3')end
        if start and due and start>0 and start<=now and now-start<2000000
            and due>now and s.last_start~=start then
            local interval=reuse and reuse-due
            assert(interval and interval>=1000000 and interval<=3600000000,
                'unsupported effective recharge interval')
            state.fire(s,start,interval)
            c.emit(string.format('SHOT charges=%d recharge=%.6f short=0',
                s.charges,interval/1000000))
        end
        local previous=s.charges;state.advance(s,now)
        if previous~=s.charges then c.emit('RECHARGED charges='..s.charges)end
        -- Re-read guards below protect against slot replacement during a poll.
        if metadata and metadata.owner_at then
            assert(c.reader.read(metadata.owner_at,8)==metadata.owner_bytes,'OPS owner changed')
        end
        assert(c.reader.read(at,32)==record:sub(1,32),'OPS slot changed')
        local count=c.reader.read(at+4,4)
        if count~=b.encode(s.charges,'u32') then c.store(at+4,count,b.encode(s.charges,'u32'))end
        local target=state.deadline(s)
        local existing=c.reader.read(at+24,8)
        local encoded=c.encode64(target)
        if existing~=encoded then c.store(at+24,existing,encoded)end
        if metadata then views[#views+1]={key=key,index=metadata.index,
            charges=s.charges,next=s.next,interval=s.interval}end
    end
    local function cancel()
        for at,value in pairs(originals)do
            if c.definition()==at and c.reader.read(at+80,4)==b.encode(3,'u32') then
                c.store(at+80,b.encode(3,'u32'),value)
            end
        end
    end
    return {prepare=prepare,slot=slot,cancel=cancel,begin=begin,finish=finish,views=function()return views end}
end
return M
