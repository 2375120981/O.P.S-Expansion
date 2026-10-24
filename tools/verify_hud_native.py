import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.lua_runner import execute,default_dll
program=''
program+='local actual_bytes=assert(loadstring('+json.dumps((ROOT/'src/local_bytes.lua').read_text(encoding='utf-8'))+'))()\n'
for name in ('hud_view','hud_locator','hud_native'):
    source=(ROOT/'src'/f'{name}.lua').read_text(encoding='utf-8')
    program+='package.preload['+json.dumps('mods/c09nat/ops_cooldown_40s/'+name)+']=function()return assert(loadstring('+json.dumps(source)+'))()end\n'
program+=r'''
local memory={};local calls={};local stores={};local base=1000000
local function enc(n)local s=''for i=1,4 do s=s..string.char(n%256);n=math.floor(n/256)end return s end
local function put(at,s)for i=1,#s do memory[at+i-1]=s:sub(i,i)end end
local function read(at,n)local s={}for i=0,n-1 do s[#s+1]=memory[at+i]or'\0'end return table.concat(s)end
local b=actual_bytes
local now=10;local r={read=read}
function r.system_info()return 4096,131072 end
function r.query(at)
 if at>base then return {base=at,size=4096,state=4096,protect=32,type=16777216}end
 return {base=65536,size=65536,state=4096,protect=4,type=131072}end
function r.monotonic_time()return now end
function r.precise_time()return 0 end
local signatures={
 [0x183ac90]='48895c2418574883ec300f2974242048',
 [0x183ae60]='48895c24104889742418574883ec3048',
 [0x143bf90]='4883ec284c8bd93991100100000f8480',
 [0x143c9d0]='40534883ec20488bd94881c110010000',
 [0x143c8d0]='4883ec284c8bd14881c110010000e8',
 [0x143b160]='4055574155488dac2430eeffffb8e012',
 [0x14508e0]='4883ec28448b014c8bd1418bc0458bc8',
 [0x1448ad0]='40574883ec20f30f104144488bf90f2e'}
for offset,hex in pairs(signatures)do put(base+offset,hex:gsub('..',function(h)return string.char(tonumber(h,16))end))end
local ffi={}
function ffi.cast(signature,at)
 if signature=='void *'then return at end
 return function(...)
  local args={...};calls[#calls+1]={rva=at-base,args=args}
  if at-base==0x143bf90 then put(args[1]+0x110,enc(args[2]))end
  if at-base==0x143c9d0 or at-base==0x143c8d0 then
   local label,key=args[1],args[2];local used=read(label+0x268,1):byte();local index
   for i=0,used-1 do if b.u32(read(label+0x118+i*24,4),0)==key then index=i;break end end
   if not index then assert(used<14,'native token capacity overflow');index=used;put(label+0x268,string.char(used+1))end
   put(label+0x118+index*24,enc(key)..enc(at-base==0x143c9d0 and args[4]+2 or 1)..enc(args[3])..string.rep('\0',12))
  end
 end
end
package.preload['mods/c09nat/ops_cooldown_40s/standalone_runtime']=function()return {ffi=ffi}end
local panel=65536+0x24e340+0x146dc0+0x1150;local widget=panel+0x7c0
local function gui(at,class)
 put(at,enc(class*262144+0x10));put(at+224,enc(98304)..enc(0))
 if class==7 then put(at+0xf8,enc(98304)..enc(0));put(at+0x2a8,enc(98304)..enc(0))end
end
gui(panel,1);gui(panel+0x25b8,7);gui(widget,1)
-- HUD manager is an aggregate whose prefix need not be a GUI class.
put(65536,enc(0xffffffff))
put(base+0x346d538,enc(65536)..enc(0))
for _,offset in ipairs({0x110,0x268,0x3c0,0x518})do gui(widget+offset,3)end
gui(widget+0x920,1);gui(widget+0xce0,7)
put(widget+0x14b8,enc(4)..enc(3)..enc(0)..enc(0)..enc(118)..enc(1))
put(panel+0x3748,enc(4)..enc(118))
put(panel+0x3758,enc(1))
local context={reader=r,bytes=b,base=base,emit=function()end,
 store=function(at,expected,value)
  assert(at==widget+0x14bc or at==panel+0x3718 or at==panel+0x3720 or
   at==panel+0x25b8 or at==262144+0x2c10+0x1348,'non-presentation memory write')
  assert(read(at,#expected)==expected);put(at,value);stores[#stores+1]=at
 end}
local native=require('mods/c09nat/ops_cooldown_40s/hud_native')
local hud=native.new(context)
local raw_read=r.read;local raw_query=r.query;local read_bytes=0;local largest=0;local query_count=0
local precise=0;local delayed=false
r.precise_time=function()return precise end
r.read=function(at,n)
 read_bytes=read_bytes+n;largest=math.max(largest,n)
 if n==24 and not delayed then delayed=true;precise=precise+0.001 end
 return raw_read(at,n)
end
r.query=function(at)
 assert(at>=65536 and at<65536+0x480000,'unanchored region enumeration')
 query_count=query_count+1;return raw_query(at)
end
local view={key='owner:slot',index=4,charges=2,next=70000000,interval=70000000}
hud.tick({view},35000000)
assert(#calls>0,'slow read starved fixed candidate discovery')
now=now+0.1
hud.tick({view},35000000)
assert(#calls>0,'cached candidate lost')
assert(read_bytes<262144 and largest<=4096 and query_count<=128,'discovery budget regression')
read_bytes=0;largest=0
assert(read(widget+0x14bc,4)==enc(2))
local function find(rva,address)
 for i=#calls,1,-1 do local row=calls[i]
  if row.rva==rva and row.args[1]==address then return row.args end
 end
end
assert(find(0x183ac90,widget)[2]==0.5,'native progress fraction incorrect')
assert(find(0x183ae60,widget),'native count update absent')
assert(find(0x143bf90,panel+0x25b8)[2]==0xab47253c,'native countdown label missing')
assert(find(0x143c9d0,panel+0x25b8)[2]==0x4583b0d3)
assert(find(0x143c9d0,panel+0x25b8)[3]==35,'countdown seconds incorrect')
view.charges=0;hud.tick({view},40000000)
assert(read_bytes<65536 and largest<=345,'cached HUD still hunting')
assert(read(widget+0x14bc,4)==enc(0),'zero badge not updated')
assert(find(0x14508e0,widget+0x920)[2]==1,'zero badge hidden')
local model=require('mods/c09nat/ops_cooldown_40s/hud_view')
local modified=model.compute({charges=1,next=59850000,interval=59850000},29925000)
assert(modified.progress==0.5 and modified.seconds==30,'modifier recharge not represented')
local rounded=model.compute({charges=1,next=61010000,interval=70000000},0)
assert(rounded.minutes==1 and rounded.seconds==2,'countdown minute carry')
view.charges=3;view.next=nil;calls={};hud.tick({view},80000000)
assert(find(0x183ac90,widget)[2]==1,'full stock progress')
assert(find(0x143bf90,panel+0x25b8)[2]==0xa851371b,'full stock did not restore native ready label')
local before=#calls;hud.tick({view,view},80000000)
assert(#calls==before,'ambiguous owner presentation updated')
put(widget+0x14c8,enc(99));hud.tick({view},80000000)
assert(#calls==before,'replaced widget invoked')
put(base+0x346d538,enc(0)..enc(0))
query_count=0;read_bytes=0;hud.tick({view},80000000)
assert(query_count==0 and read_bytes<1024 and #calls==before,'missing anchor used a global fallback')
put(base+0x183ac90,'\0');local ok=pcall(native.new,context)
assert(not ok,'modified native code signature accepted')
'''
execute(program.encode(),default_dll())
print('PASS: native GUI invocation routing, 0 badge, countdown tokens, progress, modifiers, full stock, lifetime, owner ambiguity and code guards (mock GUI; no live rendering claim)')
