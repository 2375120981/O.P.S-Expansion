"""Exercise private Win32 bindings in an offline Lua process, not the game."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.lua_runner import execute,default_dll
DLL=default_dll()
runtime=(ROOT/'src/standalone_runtime.lua').read_text(encoding='utf-8')
prefix='local module=assert(loadstring('+json.dumps(runtime)+'))();local r=module.create()\n'
native=prefix+r'''
local ffi=module.ffi
local k=ffi.load('kernel32')
local handle=k.GetModuleHandleA('kernel32.dll')
local alloc=ffi.cast('void *(*)(void *,size_t,uint32_t,uint32_t)',k.GetProcAddress(handle,'VirtualAlloc'))
local free=ffi.cast('int (*)(void *,size_t,uint32_t)',k.GetProcAddress(handle,'VirtualFree'))
local page=alloc(nil,4096,0x3000,4);assert(page~=nil)
local at=r.address(page)
local ok,why=pcall(function()
 local q=assert(r.query(at));assert(q.state==4096 and q.protect==4 and q.size>=4096)
 assert(r.write(at,'abcd'));assert(r.read(at,4)=='abcd')
 assert(r.protect(at,4096,2)==4)
 assert(r.read(at,4)=='abcd');assert(not pcall(r.write,at,'1234'))
 assert(r.protect(at,4096,4)==2)
 assert(r.write(at,'efgh'));assert(r.read(at,4)=='efgh')
 assert(not pcall(r.write,at+4092,'12345678'))
 assert(not pcall(r.write,at+1,'1234'))
 assert(not pcall(r.protect,at,4096,64))
 local size,limit=r.system_info();assert(size==4096 and limit>at)
 assert(r.precise_time()>0 and r.monotonic_time()>0)
 r.begin_budget()
 for i=1,64 do assert(r.read(at,4096))end
 local permitted,reason=pcall(r.read,at,4)
 assert(not permitted and reason==r.budget_exhausted,'aggregate read cap bypassed')
 assert(r.stats()==262144)
 r.begin_budget()
 for i=1,128 do assert(r.query(at))end
 permitted,reason=pcall(r.query,at)
 assert(not permitted and reason==r.budget_exhausted,'query cap bypassed')
 r.begin_budget();assert(r.read(at,4)=='efgh','budget did not recover')
end)
assert(free(page,0,0x8000)~=0)
if not ok then error(why)end
return r.module_hash(assert(r.module('lua51.dll')))
'''
digest=execute(native.encode(),DLL).decode()
assert digest==hashlib.sha256(DLL.read_bytes()).hexdigest().upper(),digest
print('PASS real Win32 adapter: owned test page read/write/query, data protection/restore, write bounds, clocks, SHA256 module-file hash')
source=(ROOT/'src/local_scheduler.lua').read_text(encoding='utf-8')
script=r'''
local calls=0;local cancelled=0;local logs=0
CowboyBingusModLoader={open_log=function()logs=logs+1;return {write=function()end,flush=function()end,close=function()end}end}
local prior=function(a,b)assert(a==2 and b==3);return 11,nil,13 end
update=prior
'''
script+='local scheduler=assert(loadstring('+json.dumps(source,ensure_ascii=False)+'))()\n'+r'''
local watch={status='running',tick=function()calls=calls+1 end}
function watch.cancel()cancelled=cancelled+1;watch.status='cancelled'end
scheduler.attach(watch)
local a,b,c=update(2,3);assert(a==11 and b==nil and c==13 and calls==1)
watch.tick=function()error({reason='OPS read budget exhausted'},0)end
a,b,c=update(2,3)
assert(watch.status=='running' and cancelled==0 and logs==0 and a==11 and b==nil and c==13)
watch.tick=function()error('fixture rejection')end
update(2,3);assert(cancelled==1 and watch.status=='rejected' and update==prior and logs==1)
update=nil;local count=0
local w={status='running',tick=function()count=count+1 end,cancel=function()end}
scheduler.attach(w);update();assert(count==1)
'''
execute(script.encode(),DLL)
print('PASS private scheduler: preceding callback arguments/returns, nil returns, rejection cleanup/logging, callback restoration, empty prior callback')
