-- Guarded native GUI calls only. No hooks, executable writes, or fake cooldowns.
local M={}
function M.new(c)
 local r,b,base=c.reader,c.bytes,c.base
 local ffi=require('mods/c09nat/ops_cooldown_40s/standalone_runtime').ffi
 local guards={}
 local function bind(rva,hex,signature)
  local bytes=hex:gsub('..',function(pair)return string.char(tonumber(pair,16))end)
  assert(r.read(base+rva,#bytes)==bytes,'native GUI signature mismatch: '..rva)
  local q=assert(r.query(base+rva),'native GUI code unavailable')
  assert(q.state==4096 and (q.protect==32 or q.protect==64),'native GUI target is not executable')
  guards[#guards+1]={at=base+rva,bytes=bytes}
  return ffi.cast(signature,base+rva)
 end
 local progress=bind(0x183ac90,'48895c2418574883ec300f2974242048','void (*)(void *,float,unsigned char)')
 local count=bind(0x183ae60,'48895c24104889742418574883ec3048','void (*)(void *)')
 local text=bind(0x143bf90,'4883ec284c8bd93991100100000f8480','void (*)(void *,unsigned int)')
 local number=bind(0x143c9d0,'40534883ec20488bd94881c110010000','void (*)(void *,unsigned int,int,unsigned int)')
 local visible=bind(0x14508e0,'4883ec28448b014c8bd1418bc0458bc8','void (*)(void *,unsigned char)')
 local alpha=bind(0x1448ad0,'40574883ec20f30f104144488bf90f2e','void (*)(void *,float)')
 local locator=require('mods/c09nat/ops_cooldown_40s/hud_locator').new(c)
 local model=require('mods/c09nat/ops_cooldown_40s/hud_view')
 local function pointer(at)return ffi.cast('void *',at)end
 local last_detail={};local first=true;local last_guard
 local function apply(node,now)
  local at,v=node.at,node.view;local display=model.compute(v,now)
  -- Locator validates identity and GUI children immediately before every call.
  local existing=r.read(at+0x14bc,4);local target=b.encode(display.count,'u32')
  if existing~=target then c.store(at+0x14bc,existing,target)end
  count(pointer(at)) -- explicitly includes zero; native caller normally hides it
  alpha(pointer(at+0xce0),1)
  visible(pointer(at+0x920),1)
  progress(pointer(at),display.progress,1)
  -- Keep the ordinary icon bright while stored uses remain. The progress mask
  -- is native, while the genuine count continues to control firing permission.
  alpha(pointer(at+0x518),display.available and 1 or 0.6)
  -- The detailed panel embeds the same icon at +0x7c0. Validate the relation;
  -- a main HUD icon does not automatically qualify as a detailed panel.
  local panel=at-0x7c0
  local selected=r.read(panel+0x3748,8)
  if selected and b.u32(selected,0)==v.index and b.u32(selected,4)==118 and
   locator.gui(panel,1,1) and locator.gui(panel+0x25b8,7,7) then
   local label=panel+0x25b8
   if display.recharging then
    text(pointer(label),0xab47253c) -- game's localized cooldown countdown label
    number(pointer(label),0x51d1e697,display.minutes,0x3020)
    number(pointer(label),0x4583b0d3,display.seconds,0x3020)
    visible(pointer(label),1);alpha(pointer(label),1)
    last_detail[panel]=true
   elseif last_detail[panel]then
    -- A full refill need not change the native ready state, so explicitly
    -- restore its label rather than retaining the last countdown substitution.
    local status=r.read(panel+0x3758,4)
    if status and b.u32(status,0)==1 then text(pointer(label),0xa851371b)end
    last_detail[panel]=nil
   end
  end
  if first then first=false;c.emit('HUD_NATIVE_PRESENTATION_ACTIVE')end
 end
 local function tick(views,now)
  local wall=r.monotonic_time()
  if not last_guard or wall-last_guard>=1 then
   for _,guard in ipairs(guards)do
    assert(r.read(guard.at,#guard.bytes)==guard.bytes,'native GUI code changed; HUD stopped')
   end
   last_guard=wall
  end
  -- Owner identity for multiplayer widgets has not yet been proven. Refuse
  -- ambiguous matches rather than displaying another owner's recharge state.
  if #views~=1 then locator.reset();return end
  for _,node in ipairs(locator.tick(views))do apply(node,now)end
 end
 return {tick=tick}
end
return M
