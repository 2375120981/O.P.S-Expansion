import json,struct,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.lua_runner import execute,default_dll
from tools.archive_support import resource_hash
version=(ROOT/'VERSION').read_text().strip()
path=ROOT/'build'/f'O.P.S.扩展改装件-{version}.zip'
resource='mods/c09nat/ops_cooldown_40s'
with zipfile.ZipFile(path) as z:
    manifest=json.loads(z.read('manifest.json'))
    assert manifest['Name']==f'O.P.S.扩展改装件 {version}'
    options=manifest['Options'];assert len(options)==1
    choices=options[0]['SubOptions'];assert len(choices)==2
    assert options[0]['Name']=='轨道精准攻击扩展改装选择'
    assert [(c['Name'],c['Description']) for c in choices]==[
        ('自动装弹机','基础冷却时间40s，呼叫时间固定2s不受环境影响'),
        ('待发弹药架','基础冷却时间70s，呼叫时间固定2s不受环境影响，待发弹药3发可随时补充')]
    assert [c['Include'] for c in choices]==[['Standard'],['Storage']]
    assert 'Include' not in options[0] # no common folder containing another addon
    assert json.loads(z.read('mod-info.json'))['requires']=={'bingus':{'min_release':15,'api':1}}
    for folder,expected,cooldown,storage in [('Standard',7,40,False),('Storage',12,70,True)]:
        archive=z.read(f'{folder}/9ba626afa44a3aa3.patch_0')
        types,count=struct.unpack_from('<II',archive,4);assert count==expected
        found={}
        for i in range(count):
            row=struct.unpack_from('<7Q6I',archive,72+types*32+i*80)
            assert row[1]==0xA14E8DFA2CD117E2
            body=archive[row[2]+8:row[2]+row[7]]
            found[row[0]]=body
            assert b"require('hd2runtime/" not in body and b'mods/skyeshade/hd2runtime' not in body
            script=('local f,e=loadstring('+json.dumps(body.decode('utf-8'),ensure_ascii=False)
                    +');assert(f,e);return "PASS"').encode('utf-8')
            assert execute(script,default_dll())==b'PASS'
        config=found[resource_hash(resource+'/config')].decode()
        assert f'cooldown={cooldown}' in config and f'storage={str(storage).lower()}' in config
        assert f'native_hud={str(storage).lower()}' in config
        addon=found[resource_hash(resource)]
        assert addon.startswith(('-- HD2-Addon: '+resource+'\n').encode())
        assert 'O.P.S.扩展改装件'.encode() in addon
        assert b'fixed_timing' not in addon
        assert b'OPSStandalone:' in addon and b'CowboyBingusModLoader' in addon
        print(f'PASS {folder}: {count} packaged Lua 5.1 resources, exact configuration, Chinese name')
    assert not any('fixed_timing' in n or 'timing_probe' in n for n in z.namelist())
print('PASS exclusive manager sub-options and complete package')
