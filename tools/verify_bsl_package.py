"""Load each complete shipped addon with external runtime imports forbidden."""
import json,struct,sys,zipfile
from pathlib import Path
import verify_data_timing as fixture
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.lua_runner import execute,default_dll
from tools.archive_support import resource_hash
version=(ROOT/'VERSION').read_text().strip()
resource='mods/c09nat/ops_cooldown_40s'
with zipfile.ZipFile(ROOT/'build'/f'{ROOT.name}-{version}.zip') as z:
    report=json.loads(z.read('build-report.json'))
    for folder in ('Standard','Storage'):
        a=z.read(folder+'/9ba626afa44a3aa3.patch_0');types,count=struct.unpack_from('<II',a,4)
        payload={}
        for i in range(count):
            row=struct.unpack_from('<7Q6I',a,72+types*32+i*80)
            payload[row[0]]=a[row[2]+8:row[2]+row[7]].decode('utf-8')
        script=fixture.program.split('\nlocal m=assert(loadstring')[0]
        for name in report[folder]['resources']:
            body=payload[resource_hash(name)]
            script+='package.preload['+json.dumps(name)+']=function()return assert(loadstring('+json.dumps(body,ensure_ascii=False)+'))()end\n'
        script+=r'''
local original_require=require
require=function(name)
 assert(not name:find('hd2runtime',1,true),'external runtime import: '..name)
 return original_require(name)
end
package.preload['mods/c09nat/ops_cooldown_40s/standalone_runtime']=function()return {create=function()return r end}end
local schema=require('mods/c09nat/ops_cooldown_40s/local_schema')
r.module_hash=function(name)return name=='game.dll'and schema.dll_sha or schema.exe_sha end
put(base+schema.stratagem.table_rva+118*8,u64(def))
put(def+104,b.encode(80,'f32'));put(def+80,b.encode(4294967295,'u32'))
put(slot+24,u64(86000000))
CowboyBingusModLoader.api=1;CowboyBingusModLoader.version=16
local state=require('mods/c09nat/ops_cooldown_40s')
assert(state.status=='running',state.error)
assert(type(update)=='function','private scheduler not attached')
update(0.016)
assert(read(def+104,4)==b.encode(COOLDOWN,'f32'),'base cooldown not patched')
assert(read(slot+32,8)==u64(12000000),'call time not patched')
STORAGE_ASSERTION
state.cancel();update(0.016);assert(update==nil,'private callback not restored')
assert(read(def+104,4)==b.encode(80,'f32'))
'''.replace('COOLDOWN',str(report[folder]['base_cooldown'])).replace('STORAGE_ASSERTION',
            "assert(read(slot+4,4)==b.encode(2,'u32'));assert(read(slot+24,8)==u64(0))" if folder=='Storage' else '')
        execute(script.encode(),default_dll())
        print(f'PASS shipped {folder}: BSL startup, private scheduler, cooldown/call/storage and cleanup with every external runtime import forbidden (mock game memory)')
