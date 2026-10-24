-- Bounded discovery of live OPS GUI widgets; addresses never survive a session.
local M={}
function M.new(c)
 local r,b=c.reader,c.bytes
 -- Root load at 12f53af. Gameplay UI constructed at root+24e340.
 -- 12ea110 constructs stratagem panel container +146dc0;
 -- 1833440 constructs 16 panels at +1150, stride 3760;
 -- 18375e1 identifies each panel embedded icon at +7c0.
 local root_rva=0x346d538
 local offsets={}
 for i=0,15 do offsets[#offsets+1]=0x24e340+0x146dc0+0x1150+i*0x3760+0x7c0 end
 local cursor=1;local nodes={};local root;local identity
 local next_hunt=0;local delay=0.25;local last_report=0
 local function ptr(at)
  local s=r.read(at,8);if not s then return end
  local hi=b.u32(s,4);if hi>32767 then return end
  local n=b.u32(s,0)+hi*4294967296;if n>=65536 and n%8==0 then return n end
 end
 local function gui(at,minimum,maximum)
  local s=r.read(at,256);if not s then return false end
  -- Captured GUI container/image/text classes; reject arbitrary bit patterns.
  local flags=b.u32(s,0);local class=math.floor(flags/262144)%16
  if flags>=268435456 or class<(minimum or 1) or class>(maximum or 13) then return false end
  for _,o in ipairs({224,240})do
   local p=ptr(at+o);local q=p and r.query(p)
   if q and q.state==4096 and (q.protect==2 or q.protect==4 or q.protect==8) then return true end
  end
  return false
 end
 local function valid(at,views)
  local s=r.read(at+0x14b8,24)
  if not s or b.u32(s,16)~=118 or b.u32(s,4)>3 or b.u32(s,20)>8 then return end
  local index=b.u32(s,0)
  for _,view in ipairs(views)do
   if view.index==index and gui(at,1,1) and gui(at+0x920,1,1) and gui(at+0xce0,7,7) then
    local images=true
    for _,offset in ipairs({0x110,0x268,0x3c0,0x518})do
     if not gui(at+offset,3,13)then images=false;break end
    end
    if images then return view end
   end
  end
 end
 local function tick(views)
  local now=r.monotonic_time();local ids={}
  for _,view in ipairs(views)do ids[#ids+1]=view.key..':'..view.index end
  local id=table.concat(ids,',');local anchor=ptr(c.base+root_rva)
  if id~=identity or anchor~=root then
   identity=id;root=anchor;cursor=1;nodes={};next_hunt=0;delay=0.25
   if root then c.emit('HUD_ANCHOR '..string.format('%.0f',root))end
  end
  local result={}
  for i=#nodes,1,-1 do
   local view=valid(nodes[i],views)
   if view then result[#result+1]={at=nodes[i],view=view}
   else table.remove(nodes,i);cursor=1;next_hunt=0 end
  end
  if #result>0 then return result end
  if #views==0 or now<next_hunt then return {}end
  next_hunt=now+delay
  local allocation=root and r.query(root)
  if not allocation or allocation.state~=4096 or
     (allocation.protect~=4 and allocation.protect~=8)then
   delay=math.min(5,delay*2);return {}
  end
  local deadline=r.precise_time()+0.0005;local attempts=0
  -- Always finish one bounded candidate. A slow read cannot starve discovery.
  while cursor<=#offsets and attempts<4 do
   local at=root+offsets[cursor]
   local view=valid(at,views)
   if view then
    nodes[#nodes+1]=at;result[#result+1]={at=at,view=view}
    c.emit('HUD_WIDGET_OFFSET '..string.format('0x%x',offsets[cursor]))
   end
   cursor=cursor+1;attempts=attempts+1
   if r.precise_time()>=deadline then break end
  end
  if cursor>#offsets then
   cursor=1;delay=math.min(5,delay*2);next_hunt=now+delay
   if #result==0 and now-last_report>=15 then
    c.emit('HUD_FIXED_CHAIN_MISS candidates=16');last_report=now
   end
  else next_hunt=now+0.05 end
  return result
 end
 return {tick=tick,gui=gui,reset=function()identity=nil end}
end
return M
