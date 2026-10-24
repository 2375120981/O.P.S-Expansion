import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.archive_support import zip_files
from tools.archive_support import ARCHIVE_NAME,make_archive,resource_hash,lua_resource
spec=json.loads((ROOT/'hd2runtime.json').read_text(encoding='utf-8'))
resource=spec['resource'];version=(ROOT/'VERSION').read_text().strip()
def wrap_bsl(body):
    return '-- HD2-Addon: '+resource+'\n'+'''local loader=rawget(_G,'CowboyBingusModLoader')
assert(loader and loader.api==1 and type(loader.version)=='number' and loader.version>=16,
    'Requires Bingus Shared Loader v15+ / API 1')
local key='OPSStandalone:'..'''+json.dumps(resource)+'''
local existing=rawget(_G,key)
if existing then return existing end
local function start()
'''+body+'''
end
local state=start()or true
rawset(_G,key,state)
return state
'''
variants=[('Standard','自动装弹机','基础冷却时间40s，呼叫时间固定2s不受环境影响',40,False),
          ('Storage','待发弹药架',
           '基础冷却时间70s，呼叫时间固定2s不受环境影响，待发弹药3发可随时补充',70,True)]
files={};choices=[];report={}
for folder,name,description,cooldown,storage in variants:
    sources={}
    for path in sorted((ROOT/'src').glob('*.lua')):
        if not storage and path.stem in ('storage','charge_state','hud_locator','hud_native','hud_view'):continue
        body=path.read_text(encoding='utf-8')
        if path.stem=='config':body=f'return {{cooldown={cooldown},storage={str(storage).lower()},native_hud={str(storage).lower()}}}\n'
        target=resource if path.stem=='addon' else resource+'/'+path.stem
        if path.stem=='addon':body=wrap_bsl(body)
        sources[target]=body.encode('utf-8')
    files[folder+'/'+ARCHIVE_NAME]=make_archive({resource_hash(k):lua_resource(v) for k,v in sources.items()})
    files[folder+'/'+ARCHIVE_NAME+'.stream']=b''
    files[folder+'/'+ARCHIVE_NAME+'.gpu_resources']=b''
    choices.append({'Name':name,'Description':description,'Include':[folder]})
    report[folder]={'resources':sorted(sources),'base_cooldown':cooldown,'storage':storage}
manifest={'Version':1,'Guid':spec['guid'],'Name':spec['name']+' '+version,
    'Description':'轨道精准攻击扩展改装件。仅需 BSL v15+，无需 HD2Runtime。',
    'Options':[{'Name':'轨道精准攻击扩展改装选择','Description':'选择一种改装件，切换后部署并完整重启。',
                'SubOptions':choices}]}
files['manifest.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
files['README.md']=(ROOT/'README.md').read_bytes()
files['build-report.json']=json.dumps(report,indent=2).encode()
files['mod-info.json']=json.dumps({k:v for k,v in spec.items() if k not in ('sdk','ide_library')},ensure_ascii=False,indent=2).encode('utf-8')
out=ROOT/'build'/f'O.P.S.扩展改装件-{version}.zip';zip_files(out,files)
print(str(out))
