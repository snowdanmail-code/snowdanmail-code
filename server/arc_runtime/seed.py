"""Extend inherited v0.7 lab checkpoint, append two v0.8 policy profiles."""
from pathlib import Path
import json
from arc_versions.registry import VersionRegistry, encode
from .release import standard_policy


def seed_lab(registry_path: str | Path) -> dict:
    reg=VersionRegistry(registry_path, lab_mode=True,safe_to_switch=lambda:True)
    configs=(('0.8.0',standard_policy('balanced-read-only',.82,2)),
             ('0.8.1',standard_policy('strict-read-only',.94,3)))
    for version, policy in configs:
        reg.register_artifact('runtime_policy',version,encode(policy),requires={'contracts':'1.0.0'})
    origin=reg.get_release('demo-baseline-v0.6')
    for idx, (version,_) in enumerate(configs):
        rid=f'demo-runtime-v0.8-{idx}'
        cp=f'cp-demo-runtime-v0.8-{idx}'
        components={**origin['components'],'runtime_policy':version}
        reg.create_release(rid,components,description='Read-only pinned observation policy')
        reg.create_checkpoint(cp,rid,
            test_report={'release_id':rid,'passed':True,'total_tests':1,'failures':0,
                         'scope':'registry_lab','note':'LAB configuration validation, not device proof'},
            approved_by='local-lab',parent='cp-demo-baseline' if idx==0 else 'cp-demo-runtime-v0.8-0')
    reg.activate('cp-demo-runtime-v0.8-0')
    return reg.status()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('registry')
    args=p.parse_args()
    print(json.dumps(seed_lab(args.registry),indent=2,ensure_ascii=False))
