"""Offline-only CLI. Run `python -m arc_versions.cli --help` from server/.

No remote command endpoints. --demo-offline ONLY permits local demonstration
of the registry; it is NOT evidence that real poker tables are closed.
"""
import argparse
import json
from pathlib import Path
from .registry import VersionRegistry, RegistryError


def main(argv=None):
    p = argparse.ArgumentParser(description='AI Remote Control offline checkpoint manager')
    p.add_argument('--dir', default='./release-registry', help='local release database')
    p.add_argument('--demo-offline', action='store_true', help='LAB ONLY: simulate verified no-open-tables')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    a = sub.add_parser('register'); a.add_argument('component'); a.add_argument('version'); a.add_argument('file')
    a.add_argument('--requires', default='{}', help='exact version dependencies JSON')
    a = sub.add_parser('release'); a.add_argument('id'); a.add_argument('components_json')
    a.add_argument('--description', default=''); a.add_argument('--model', default='')
    a = sub.add_parser('checkpoint'); a.add_argument('id'); a.add_argument('release'); a.add_argument('report_json')
    a.add_argument('--approved-by', required=True); a.add_argument('--parent')
    a = sub.add_parser('activate'); a.add_argument('checkpoint'); a.add_argument('--models-checked', default='')
    a = sub.add_parser('module-draft'); a.add_argument('checkpoint'); a.add_argument('component')
    a.add_argument('version'); a.add_argument('release_id')
    sub.add_parser('verify-audit')
    args = p.parse_args(argv)
    mgr = VersionRegistry(args.dir, safe_to_switch=lambda: args.demo_offline, lab_mode=args.demo_offline)
    try:
        if args.command == 'status': result = mgr.status()
        elif args.command == 'register':
            result = mgr.register_artifact(args.component, args.version, Path(args.file).read_bytes(),
                                           requires=json.loads(args.requires))
        elif args.command == 'release':
            result = mgr.create_release(args.id, json.loads(args.components_json),
                                        description=args.description, external_model=args.model)
        elif args.command == 'checkpoint':
            result = mgr.create_checkpoint(args.id, args.release,
                        test_report=json.loads(Path(args.report_json).read_text(encoding='utf8')),
                        approved_by=args.approved_by, parent=args.parent)
        elif args.command == 'activate':
            result = mgr.activate(args.checkpoint,
                     available_models=set(args.models_checked.split(',')) if args.models_checked else set())
        elif args.command == 'module-draft':
            result = mgr.draft_module_rollback(args.checkpoint, args.component,
                                               args.version, args.release_id)
        else: result = mgr.verify_audit()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (RegistryError, ValueError, OSError) as exc:
        print(json.dumps({'ok': False, 'reason': str(exc)}, ensure_ascii=False))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
