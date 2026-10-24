-- Private Windows adapter for this addon. No external runtime resources.
local ffi=require('ffi')
assert(ffi.abi('64bit'),'Windows x64 LuaJIT FFI is required')
local cache=rawget(_G,'OPSStandaloneWin32V1')
if cache then return cache end
ffi.cdef[[
 void *GetModuleHandleA(const char *);
 void *GetProcAddress(void *,const char *);
 typedef struct OPS_MemoryInfo {
  void *base;void *allocation;uint32_t allocation_protect;
  uint16_t partition;uint16_t padding;size_t size;
  uint32_t state;uint32_t protect;uint32_t type;
 } OPS_MemoryInfo;
 typedef struct OPS_SystemInfo {
  uint32_t oem;uint32_t page;void *minimum;void *maximum;size_t mask;
  uint32_t count;uint32_t processor;uint32_t granularity;
  uint16_t level;uint16_t revision;
 } OPS_SystemInfo;
]]
assert(ffi.sizeof('OPS_MemoryInfo')==48 and ffi.sizeof('OPS_SystemInfo')==48,'unsupported Windows layout')
local kernel=ffi.load('kernel32');local crypto=ffi.load('bcrypt')
local function bind(library,name,signature)
 local module=assert(kernel.GetModuleHandleA(library),library..' unavailable')
 local address=kernel.GetProcAddress(module,name)
 assert(address~=nil,'missing Windows export '..name)
 return ffi.cast(signature,address)
end
local function k(name,signature)return bind('kernel32.dll',name,signature)end
local function bc(name,signature)return bind('bcrypt.dll',name,signature)end
local process=k('GetCurrentProcess','void *(*)(void)')()
local read=k('ReadProcessMemory','int (*)(void *,const void *,void *,size_t,size_t *)')
local write=k('WriteProcessMemory','int (*)(void *,void *,const void *,size_t,size_t *)')
local query=k('VirtualQuery','size_t (*)(const void *,void *,size_t)')
local protect=k('VirtualProtect','int (*)(void *,size_t,uint32_t,uint32_t *)')
local info=k('GetSystemInfo','void (*)(void *)')
local milliseconds=k('GetTickCount64','uint64_t (*)(void)')
local counter=k('QueryPerformanceCounter','int (*)(int64_t *)')
local frequency=k('QueryPerformanceFrequency','int (*)(int64_t *)')
local filename=k('GetModuleFileNameW','uint32_t (*)(void *,uint16_t *,uint32_t)')
local open=k('CreateFileW','void *(*)(const uint16_t *,uint32_t,uint32_t,void *,uint32_t,uint32_t,void *)')
local read_file=k('ReadFile','int (*)(void *,void *,uint32_t,uint32_t *,void *)')
local close=k('CloseHandle','int (*)(void *)')
local algorithm_open=bc('BCryptOpenAlgorithmProvider','int32_t (*)(void **,const uint16_t *,const uint16_t *,uint32_t)')
local algorithm_close=bc('BCryptCloseAlgorithmProvider','int32_t (*)(void *,uint32_t)')
local hash_create=bc('BCryptCreateHash','int32_t (*)(void *,void **,void *,uint32_t,const void *,uint32_t,uint32_t)')
local hash_update=bc('BCryptHashData','int32_t (*)(void *,const void *,uint32_t,uint32_t)')
local hash_finish=bc('BCryptFinishHash','int32_t (*)(void *,void *,uint32_t,uint32_t)')
local hash_destroy=bc('BCryptDestroyHash','int32_t (*)(void *)')
local M={ffi=ffi,_libraries={kernel,crypto}}
function M.create()
 local r={};local count=ffi.new('size_t[1]');local region=ffi.new('OPS_MemoryInfo[1]')
 local budget;local used=0;local queries=0
 r.budget_exhausted={reason='OPS read budget exhausted'}
 function r.begin_budget()budget=262144;used=0;queries=0 end
 function r.stats()return used,queries end
 local ticks=ffi.new('int64_t[1]');assert(frequency(ticks)~=0,'clock unavailable')
 local rate=tonumber(ticks[0])
 function r.module(name)local handle=kernel.GetModuleHandleA(name);if handle~=nil then return handle end end
 function r.address(handle)return tonumber(ffi.cast('uintptr_t',handle))end
 function r.read(address,size)
  assert(type(address)=='number' and address>=65536 and size>0 and size<=1048576,'read bounds')
  if budget and used+size>budget then error(r.budget_exhausted,0)end
  used=used+size
  local buffer=ffi.new('uint8_t[?]',size);count[0]=0
  if read(process,ffi.cast('const void *',address),buffer,size,count)==0 or count[0]~=size then return end
  return ffi.string(buffer,size)
 end
 function r.query(address)
  if budget and queries>=128 then error(r.budget_exhausted,0)end
  queries=queries+1
  if query(ffi.cast('const void *',address),region,ffi.sizeof(region[0]))~=ffi.sizeof(region[0])then return end
  local q=region[0]
  return {base=r.address(q.base),allocation_base=r.address(q.allocation),size=tonumber(q.size),
   state=tonumber(q.state),protect=tonumber(q.protect),type=tonumber(q.type)}
 end
 function r.write(address,data)
  assert(address>=65536 and address%4==0 and (#data==4 or #data==8 or #data==12),'write extent')
  local q=assert(r.query(address),'write region unavailable')
  assert(q.state==4096 and (q.protect==4 or q.protect==8) and
   address+#data<=q.base+q.size and address%4096+#data<=4096,'write requires a bounded writable data page')
  count[0]=0
  return write(process,ffi.cast('void *',address),data,#data,count)~=0 and count[0]==#data
 end
 function r.protect(page,size,value)
  assert(page>=65536 and page%4096==0 and size==4096 and (value==2 or value==4),'protection extent')
  local q=assert(r.query(page),'protection region unavailable')
  assert(q.state==4096 and (q.protect==2 or q.protect==4) and page+size<=q.base+q.size,'only data page protections supported')
  local old=ffi.new('uint32_t[1]')
  if protect(ffi.cast('void *',page),size,value,old)~=0 then return tonumber(old[0])end
 end
 function r.system_info()
  local s=ffi.new('OPS_SystemInfo[1]');info(s)
  return tonumber(s[0].page),r.address(s[0].maximum)+1
 end
 function r.monotonic_time()return tonumber(milliseconds())/1000 end
 function r.precise_time()assert(counter(ticks)~=0,'clock read failed');return tonumber(ticks[0])/rate end
 function r.module_hash(module)
  local path=ffi.new('uint16_t[32768]');local length=filename(module,path,32768)
  assert(length>0 and length<32768,'module path unavailable')
  local file=open(path,0x80000000,7,nil,3,0,nil)
  assert(file~=ffi.cast('void *',-1) and file~=nil,'module file unavailable')
  local algorithm=ffi.new('void *[1]');local hash=ffi.new('void *[1]')
  local ok,result=pcall(function()
   local name=ffi.new('uint16_t[7]',{83,72,65,50,53,54,0})
   assert(algorithm_open(algorithm,name,nil,0)==0,'SHA256 provider unavailable')
   assert(hash_create(algorithm[0],hash,nil,0,nil,0,0)==0,'SHA256 initialization failed')
   local buffer=ffi.new('uint8_t[1048576]');local size=ffi.new('uint32_t[1]')
   repeat
    assert(read_file(file,buffer,1048576,size,nil)~=0,'module file read failed')
    if size[0]>0 then assert(hash_update(hash[0],buffer,size[0],0)==0,'SHA256 update failed')end
   until size[0]==0
   local digest=ffi.new('uint8_t[32]');assert(hash_finish(hash[0],digest,32,0)==0,'SHA256 finalization failed')
   return (ffi.string(digest,32):gsub('.',function(ch)return string.format('%02X',ch:byte())end))
  end)
  if hash[0]~=nil then hash_destroy(hash[0])end
  if algorithm[0]~=nil then algorithm_close(algorithm[0],0)end
  close(file)
  if not ok then error(result)end
  return result
 end
 return r
end
rawset(_G,'OPSStandaloneWin32V1',M)
return M
