import json,sys
from pathlib import Path
import verify_data_timing as fixture
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.lua_runner import execute,default_dll
prefix=fixture.program.split('\nlocal m=assert(loadstring')[0]
body='local m=assert(loadstring('+json.dumps(fixture.source)+'))();\n'
for cooldown in (40,70):
    script=prefix+body+f"put(def+104,b.encode(80,'f32'));m.start({{cooldown={cooldown}}});\n"+r'''
watch.tick();assert(#writes==3)
assert(read(def+104,4)==b.encode(COOLDOWN,'f32'))
assert(read(def+84,4)==b.encode(0,'f32'))
assert(read(slot+32,8)==u64(12000000))
watch.tick();assert(#writes==3,'base patch repeatedly written')
watch.cancel();assert(read(def+104,4)==b.encode(80,'f32'))
assert(read(def+84,4)==b.encode(2,'f32'))
local prior=#writes;put(def+104,b.encode(99,'f32'));m.start({cooldown=COOLDOWN})
assert(not pcall(watch.tick));assert(#writes==prior,'conflicting cooldown changed data')
'''.replace('COOLDOWN',str(cooldown))
    execute(script.encode(),default_dll())
print('PASS independent 40/70 base cooldown patch, repeated verification, timing retained, restoration and conflicting-data refusal')
