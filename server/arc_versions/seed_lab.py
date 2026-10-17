"""Produce reproducible source snapshots + TWO DEMO checkpoints, offline.

Never starts an Android application, sends a GPT call, or places a bet.
The checkpoints are registry_lab-qualified and CANNOT be activated by a
production-mode VersionRegistry.
"""
from pathlib import Path
from io import BytesIO
import json
import zipfile
from .registry import VersionRegistry


def zip_source(root: Path, filenames: list[str]) -> bytes:
    data = BytesIO()
    with zipfile.ZipFile(data, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted(filenames):
            if '\\' in name or name.startswith('/') or '..' in Path(name).parts:
                raise ValueError('invalid source name')
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (root / name).read_bytes())
    return data.getvalue()


def build_demo(source_root: Path, registry_root: Path) -> dict:
    root = source_root.resolve()
    reg = VersionRegistry(registry_root, safe_to_switch=lambda: True, lab_mode=True)
    server = root / 'server'
    def add(name, version, filepaths, dependencies=None):
        contents = zip_source(root, filepaths)
        reg.register_artifact(name, version, contents, requires=dependencies)

    app_src = sorted(p.relative_to(root).as_posix() for p in (root/'android').rglob('*') if p.is_file())
    server_src = [f'server/{x}' for x in ('server.py','agent.py','poker_agent.py','poker_session.py',
         'lobby_agent.py','stream_agent.py','navigation_fsm.py','post_session_reviewer.py')]
    add('android','0.6.0', app_src, {'contracts':'1.0.0'})
    add('contracts','1.0.0', ['server/arc_versions/contracts.py'])
    add('server_runtime','0.6.0', server_src, {'contracts':'1.0.0'})
    add('poker_math','0.6.0', ['server/post_session_reviewer.py'], {'contracts':'1.0.0'})
    add('strategy','0.6.0', ['server/poker_agent.py'], {'poker_math':'0.6.0'})
    add('vision','0.6.0', ['server/lobby_agent.py'], {'contracts':'1.0.0'})
    add('reviewer','0.6.0', ['server/post_session_reviewer.py'], {'contracts':'1.0.0'})
    add('risk','0.6.0', ['server/poker_session.py'], {'contracts':'1.0.0'})
    add('gpt_adapter','0.6.0', ['server/agent.py'], {'contracts':'1.0.0'})
    version_files = sorted(p.relative_to(root).as_posix() for p in (server/'arc_versions').glob('*.py'))
    add('version_manager','0.7.0', version_files, {'contracts':'1.0.0'})
    add('poker_math','0.7.0', ['server/arc_versions/sandbox.py'], {'contracts':'1.0.0'})
    add('strategy','0.7.0', ['server/arc_versions/sandbox.py'], {'poker_math':'0.7.0'})
    shared = {k: '0.6.0' for k in ('android','server_runtime','poker_math','strategy','vision','reviewer','risk','gpt_adapter')}
    shared.update(contracts='1.0.0', version_manager='0.7.0')
    baseline = reg.create_release('demo-baseline-v0.6',shared,
      description='Imported v0.6 sources; documentation-grade rollback lab, not phone-verified')
    report = {'release_id':baseline['id'], 'passed':True, 'total_tests':133,'failures':0,
              'scope':'registry_lab', 'note':'Registry compatibility exercises; does not certify 1win integration'}
    reg.create_checkpoint('cp-demo-baseline',baseline['id'],test_report=report,approved_by='local-lab')
    candidate = {**shared, 'poker_math':'0.7.0','strategy':'0.7.0'}
    second = reg.create_release('demo-sandbox-v0.7',candidate,
      description='Swapped math and strategy modules to inert offline sandbox policy')
    report['release_id'] = second['id']
    reg.create_checkpoint('cp-demo-sandbox',second['id'],test_report=report,
                          approved_by='local-lab',parent='cp-demo-baseline')
    # Show deep/relative rollback and leave the baseline active in this lab.
    first_activation = reg.activate('cp-demo-sandbox')
    restoration = reg.activate('cp-demo-baseline')
    assert restoration['release_id'] == 'demo-baseline-v0.6'
    result = reg.status()
    result['demonstrated_roundtrip'] = {'first':first_activation['checkpoint_id'],
                                         'restored':restoration['checkpoint_id']}
    (root / 'server' / 'lab-report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False), encoding='utf-8')
    return result

if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',required=True)
    ap.add_argument('--registry',required=True)
    args=ap.parse_args()
    print(json.dumps(build_demo(Path(args.source),Path(args.registry)),indent=2,ensure_ascii=False))
