import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.lua_runner import execute,default_dll
import verify_data_timing as fixture
def preload(name,path):
    return 'package.preload['+json.dumps(name)+']=function()return assert(loadstring('+json.dumps(path.read_text(encoding='utf-8'))+'))()end\n'
prefix=fixture.program.split('\nlocal m=assert(loadstring')[0]
prefix=prefix.replace('put(slot+24,u64(48000000))','put(slot+24,u64(86000000))')
prefix+=preload('mods/c09nat/ops_cooldown_40s/charge_state',ROOT/'src/charge_state.lua')
prefix+=preload('mods/c09nat/ops_cooldown_40s/storage',ROOT/'src/storage.lua')
prefix+='put(def+80,b.encode(4294967295,"u32"))\n'
program=prefix+'local m=assert(loadstring('+json.dumps(fixture.source)+'))();m.start({storage=true});\n'+r'''
watch.tick()
assert(read(def+80,4)==b.encode(3,'u32'))
assert(read(slot+4,4)==b.encode(2,'u32'))
assert(read(slot+24,8)==u64(0))
assert(read(slot+32,8)==u64(12000000))
assert(read(other+32,8)==u64(18000000))
local function fire(start,interval)
 put(clock+24,u64(start+100000));put(slot+16,u64(start))
 put(slot+32,u64(start+6000000));put(slot+24,u64(start+6000000+interval))
 local count=b.u32(read(slot+4,4),0);put(slot+4,b.encode(count-1,'u32'))
 watch.tick()
end
fire(16000000,70000000);assert(read(slot+4,4)==b.encode(1,'u32'))
assert(read(slot+24,8)==u64(0))
fire(22000000,70000000);assert(read(slot+4,4)==b.encode(0,'u32'))
assert(read(slot+24,8)==u64(80000000)) -- first consumption anchors regeneration
put(clock+24,u64(80000000));watch.tick();assert(read(slot+4,4)==b.encode(1,'u32'))
fire(81000000,59500000) -- a native 15% reduction must also affect short interval
assert(read(slot+4,4)==b.encode(0,'u32'))
assert(read(slot+24,8)==u64(150000000)) -- another shot cannot reset existing recharge
put(clock+24,u64(290000000));watch.tick();assert(read(slot+4,4)==b.encode(3,'u32'))
fire(291000000,105000000) -- native 50% longer cooldown
assert(read(slot+24,8)==u64(0)) -- stored charge remains available without a short cooldown
fire(291100000,105000000);assert(read(slot+4,4)==b.encode(1,'u32'))
assert(read(slot+24,8)==u64(0)) -- back-to-back call 0.1 seconds later
-- Owner disappears and returns: a new deployment starts full again.
put(manager+184832,b.encode(0,'u32'));watch.tick()
put(manager+184832,b.encode(1,'u32'));put(slot+16,u64(0));put(clock+24,u64(310000000))
watch.tick();assert(read(slot+4,4)==b.encode(3,'u32'))
watch.cancel();assert(read(def+80,4)==b.encode(4294967295,'u32'))
assert(read(def+84,4)==b.encode(2,'f32'))
return 'PASS storage integration: 3 charges, no short gating, serial 70s recovery, no progress reset, 15%/50% recharge modifiers, cap, owner reset and restore'
'''
print(execute(program.encode(),default_dll()).decode())
for failure in ('initialize','update'):
    injection='''package.preload['mods/c09nat/ops_cooldown_40s/hud_native']=function()
return {new=function()
'''
    if failure=='initialize':
        injection+="error('fixture GUI signature mismatch')\n"
    else:
        injection+='''return {tick=function(views,now)
assert(#views==1 and views[1].index==0 and views[1].charges==2)
assert(views[1].next==80000000 and views[1].interval==70000000)
error('fixture widget unavailable')end}
'''
    injection+='end}end\n'
    isolated=injection+program.replace('m.start({storage=true})','m.start({storage=true,native_hud=true})')
    execute(isolated.encode(),default_dll())
print('PASS GUI initialization/update rejection leaves all storage mechanics and restore checks passing')
