import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.lua_runner import execute,default_dll
source=(ROOT/'src/data_timing.lua').read_text(encoding='utf-8')
byte_source=(ROOT/'src/local_bytes.lua').read_text()
program='local b=assert(loadstring('+json.dumps(byte_source)+'))();\n'+r'''
local mem={};local writes={};local protections={};local watch
local base,def,manager,clock=1000000,2000000,3000000,4000000
local function put(at,s)for i=1,#s do mem[at+i-1]=s:sub(i,i)end end
local function read(at,n)local s={};for i=0,n-1 do s[#s+1]=mem[at+i]or'\0'end;return table.concat(s)end
local function u64(n)return b.encode(n%4294967296,'u32')..b.encode(math.floor(n/4294967296),'u32')end
put(base+100+118*8,u64(def));put(def,b.encode(118,'u32')..b.encode(3523620028,'u32'))
put(def+84,b.encode(2,'f32'));put(base+55037520,u64(manager));put(base+53633864,u64(clock))
put(clock+24,u64(10100000));put(manager+184832,b.encode(1,'u32'))
local entry=manager+56;put(entry+1928,b.encode(2,'u32'))
local slot=entry+392;put(slot,b.encode(118,'u32'));put(slot+16,u64(10000000))
put(slot+24,u64(48000000));put(slot+32,u64(16000000))
local other=slot+48;put(other,b.encode(117,'u32'));put(other+16,u64(10000000));put(other+32,u64(18000000))
local r={module=function(n)return n end,module_hash=function(n)return n=='game.dll'and'dll'or'exe'end,
address=function()return base end,read=read,
query=function(at)return {state=0x1000,protect=2,base=at-at%4096,size=4096}end,
protect=function(page,n,p)protections[#protections+1]=p;return p==4 and 2 or 4 end,
write=function(at,s)writes[#writes+1]={at=at,s=s};put(at,s);return true end}
CowboyBingusModLoader={open_log=function()return {write=function()end,flush=function()end,close=function()end}end}
package.preload['mods/c09nat/ops_cooldown_40s/standalone_runtime']=function()return {create=function()return r end}end
package.preload['mods/c09nat/ops_cooldown_40s/local_bytes']=function()return b end
package.preload['mods/c09nat/ops_cooldown_40s/local_schema']=function()return {dll_sha='dll',exe_sha='exe',stratagem={table_rva=100}}end
package.preload['mods/c09nat/ops_cooldown_40s/local_scheduler']=function()return {attach=function(w)watch=w end}end
'''
program+='\nlocal m=assert(loadstring('+json.dumps(source)+'))();m.start();\n'+r'''
watch.tick();assert(#writes==2);assert(read(def+84,4)==b.encode(0,'f32'))
assert(read(slot+32,8)==u64(12000000));assert(read(slot+24,8)==u64(48000000))
assert(read(other+32,8)==u64(18000000));watch.tick();assert(#writes==2)
put(clock+24,u64(20100000));put(slot+16,u64(20000000));put(slot+32,u64(21000000))
watch.tick();assert(read(slot+32,8)==u64(22000000));assert(#writes==3)
put(slot+32,string.rep('\255',8));put(slot+16,u64(20100000));watch.tick();assert(#writes==3)
watch.cancel();assert(read(def+84,4)==b.encode(2,'f32'))
for i,v in ipairs(protections)do assert(v==(i%2==1 and 4 or 2))end
local prior=#writes;r.module_hash=function()return 'unsupported'end
assert(not pcall(m.start));assert(#writes==prior)
return 'PASS Lua 5.1: data-only writes, fixed start deadline, other slots/cooldown untouched, repeat calls, sentinels, restore, hash refusal'
'''
print(execute(program.encode(),default_dll()).decode())
