"""Local immutable artifact/checkpoint registry. Python standard library only.

CAUTION: This prototype is an offline release manager, NOT a secure deployment
controller. Android APK signing, a remote approval service and proof of actual
1win table closure are not implemented. All mutations require a supplied
trusted local safe-state callback. Remote network clients cannot promote builds.
"""
from __future__ import annotations
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from datetime import datetime, timezone
from typing import Callable
import fcntl
import json
import os
import re
import tempfile
import threading

COMPONENT = re.compile(r'^[a-z][a-z0-9_]{1,39}$')
VERSION = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
IDENTIFIER = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,79}$')
SHA = re.compile(r'^[0-9a-f]{64}$')

class RegistryError(ValueError): pass
class CompatibilityError(RegistryError): pass
class UnsafeSwitch(RegistryError): pass
class AuditError(RegistryError): pass

def encode(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def digest(data: bytes) -> str:
    return sha256(data).hexdigest()

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

class VersionRegistry:
    """Release manager that switches only in a verified offline state.

    `safe_to_switch` must be a **trusted runtime gate** (not an LLM output,
    remote screenshot or unverified operator claim). Defaults to fail-closed.
    """
    def __init__(self, root: str | Path, *, safe_to_switch: Callable[[], bool] | None = None,
                 lab_mode: bool = False):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for dirname in ('blobs', 'releases', 'checkpoints'):
            (self.root / dirname).mkdir(exist_ok=True)
        self.safe_to_switch = safe_to_switch or (lambda: False)
        self.lab_mode = lab_mode
        self.lock = threading.RLock()
        self._depth = 0
        (self.root / '.lock').touch(exist_ok=True)

    @contextmanager
    def transaction(self):
        # Reentrant per instance: do not lock flock twice on independent file
        # descriptors (that would block even when called from the same thread).
        with self.lock:
            if self._depth:
                self._depth += 1
                try:
                    yield
                finally:
                    self._depth -= 1
                return
            with (self.root / '.lock').open('r+b') as fd:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
                self._depth = 1
                try:
                    yield
                finally:
                    self._depth = 0
                    fcntl.flock(fd.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _read(path: Path, default=None):
        if not path.exists():
            return default
        return json.loads(path.read_bytes())

    @staticmethod
    def _atomic(path: Path, content: bytes):
        fd, temp = tempfile.mkstemp(prefix='.write-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(content)
                f.flush(); os.fsync(f.fileno())
            os.replace(temp, path)
            # Sync directory metadata so the rename survives abrupt power loss.
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(directory_fd)
            finally: os.close(directory_fd)
        finally:
            if os.path.exists(temp): os.unlink(temp)

    @classmethod
    def _immutable(cls, path: Path, obj: dict):
        content = encode(obj)
        if path.exists():
            if path.read_bytes() == content:
                return
            raise RegistryError(f'immutable_record_exists:{path.name}')
        cls._atomic(path, content)

    def _append_audit(self, event: str, details: dict):
        """Hash-linked audit log; detects accidental/history modification, not malicious admins."""
        p = self.root / 'audit.jsonl'
        events = self._audit_entries()
        prev = events[-1]['hash'] if events else '0' * 64
        rec = {'seq': len(events) + 1, 'time': utc_now(), 'event': event,
               'details': details, 'prev_hash': prev}
        rec['hash'] = digest(encode(rec))
        with p.open('ab') as f:
            f.write(encode(rec) + b'\n')
            f.flush(); os.fsync(f.fileno())

    def _audit_entries(self):
        p = self.root / 'audit.jsonl'
        if not p.exists(): return []
        entries = []
        prev = '0' * 64
        with p.open('rb') as f:
            for index, line in enumerate(f, 1):
                try: item = json.loads(line)
                except (ValueError, UnicodeError): raise AuditError('corrupt_audit_json') from None
                h = item.pop('hash', None)
                valid = (item.get('seq') == index and item.get('prev_hash') == prev
                         and h is not None and digest(encode(item)) == h)
                if not valid: raise AuditError(f'audit_chain_broken_at:{index}')
                item['hash'] = h
                entries.append(item)
                prev = h
        return entries

    def verify_audit(self) -> dict:
        with self.transaction():
            items = self._audit_entries()
            return {'ok': True, 'events': len(items), 'tip': items[-1]['hash'] if items else None}

    def register_artifact(self, component: str, version: str, contents: bytes, *,
                          contract_major: int = 1, requires: dict[str, str] | None = None) -> dict:
        if not COMPONENT.fullmatch(component) or not VERSION.fullmatch(version):
            raise RegistryError('invalid_component_or_version')
        if type(contents) is not bytes or not 0 < len(contents) <= 20_000_000:
            raise RegistryError('invalid_artifact_size')
        if type(contract_major) is not int or contract_major < 1:
            raise RegistryError('invalid_contract')
        requires = requires if requires is not None else {}
        if not isinstance(requires, dict) or any(not COMPONENT.fullmatch(c) or not VERSION.fullmatch(v)
                                                   for c, v in requires.items()):
            raise RegistryError('invalid_dependencies')
        h = digest(contents)
        key = f'{component}@{version}'
        rec = {'key': key, 'component': component, 'version': version, 'sha256': h,
               'size': len(contents), 'contract_major': contract_major, 'requires': requires}
        with self.transaction():
            self._audit_entries()  # fail closed if the audit trail is corrupt
            index = self._read(self.root / 'artifacts.json', {})
            if key in index and index[key] != rec:
                raise RegistryError('immutable_version_conflict')
            blob = self.root / 'blobs' / h
            if blob.exists():
                if digest(blob.read_bytes()) != h: raise RegistryError('corrupt_blob')
            else:
                self._immutable_blob(blob, contents)
            if key not in index:
                index[key] = rec
                self._atomic(self.root / 'artifacts.json', encode(index))
                self._append_audit('artifact_registered', {'key': key, 'sha256': h})
            return rec

    @classmethod
    def _immutable_blob(cls, path: Path, contents: bytes):
        if path.exists():
            if path.read_bytes() != contents: raise RegistryError('corrupt_blob')
            return
        cls._atomic(path, contents)

    def verify_release(self, release: dict) -> bool:
        index = self._read(self.root / 'artifacts.json', {})
        components = release.get('components')
        if not isinstance(components, dict) or not components:
            raise CompatibilityError('no_components')
        if type(release.get('contract_major')) is not int:
            raise CompatibilityError('contract_missing')
        for comp, version in components.items():
            record = index.get(f'{comp}@{version}')
            if record is None: raise CompatibilityError(f'missing_component:{comp}@{version}')
            if record['contract_major'] != release['contract_major']:
                raise CompatibilityError(f'contract_mismatch:{comp}')
            blob = self.root / 'blobs' / record['sha256']
            if not blob.is_file() or digest(blob.read_bytes()) != record['sha256']:
                raise CompatibilityError(f'blob_missing_or_modified:{comp}')
            for dep, dep_version in record['requires'].items():
                if components.get(dep) != dep_version:
                    raise CompatibilityError(f'dependency_mismatch:{comp}->{dep}@{dep_version}')
        return True

    def create_release(self, release_id: str, components: dict[str, str], *,
                       contract_major: int = 1, description: str = '', external_model: str = '') -> dict:
        if not IDENTIFIER.fullmatch(release_id): raise RegistryError('invalid_release_id')
        if not isinstance(components, dict) or any(not COMPONENT.fullmatch(c) or not VERSION.fullmatch(v)
                                                    for c, v in components.items()):
            raise RegistryError('invalid_components')
        if not isinstance(description, str) or len(description) > 300:
            raise RegistryError('invalid_description')
        if not isinstance(external_model, str) or len(external_model) > 80:
            raise RegistryError('invalid_model_pin')
        rec = {'id': release_id, 'components': components, 'contract_major': contract_major,
               'description': description, 'external_model': external_model}
        with self.transaction():
            self._audit_entries()
            self.verify_release(rec)
            path = self.root / 'releases' / f'{release_id}.json'
            if path.exists():
                if path.read_bytes() != encode(rec): raise RegistryError('immutable_release_conflict')
                return rec
            self._immutable(path, rec)
            self._append_audit('release_created', {'id': release_id})
            return rec

    def create_checkpoint(self, checkpoint_id: str, release_id: str, *, test_report: dict,
                          approved_by: str, parent: str | None = None) -> dict:
        if not IDENTIFIER.fullmatch(checkpoint_id) or not IDENTIFIER.fullmatch(release_id):
            raise RegistryError('bad_checkpoint_or_release_id')
        if not isinstance(approved_by, str) or not 3 <= len(approved_by) <= 80:
            raise RegistryError('approval_required')
        if (not isinstance(test_report, dict) or test_report.get('release_id') != release_id
                or test_report.get('passed') is not True or type(test_report.get('total_tests')) is not int
                or test_report['total_tests'] < 1 or test_report.get('failures') != 0):
            raise RegistryError('passing_test_evidence_required')
        if parent is not None and not IDENTIFIER.fullmatch(parent):
            raise RegistryError('invalid_parent')
        with self.transaction():
            self._audit_entries()
            if parent and not (self.root / 'checkpoints' / f'{parent}.json').exists():
                raise RegistryError('missing_parent')
            release = self.get_release(release_id)
            self.verify_release(release)
            scope = test_report.get('scope', 'registry_lab')
            if scope not in ('registry_lab', 'integration'):
                raise RegistryError('invalid_test_scope')
            if scope == 'integration' and test_report.get('device_test_passed') is not True:
                raise RegistryError('device_test_evidence_required')
            report_hash = digest(encode(test_report))
            self._immutable_blob(self.root / 'blobs' / report_hash, encode(test_report))
            rec = {'id': checkpoint_id, 'release_id': release_id, 'created_utc': utc_now(),
                   'parent': parent, 'approved_by': approved_by,
                   'release_hash': digest(encode(release)),
                   'test_report_hash': report_hash, 'scope': scope, 'status': 'verified'}
            self._immutable(self.root / 'checkpoints' / f'{checkpoint_id}.json', rec)
            self._append_audit('checkpoint_created', {'id': checkpoint_id, 'release': release_id})
            return rec

    def get_release(self, release_id: str) -> dict:
        if not IDENTIFIER.fullmatch(release_id): raise RegistryError('bad_release_id')
        rec = self._read(self.root / 'releases' / f'{release_id}.json')
        if rec is None: raise RegistryError('unknown_release')
        return rec

    def get_checkpoint(self, checkpoint_id: str) -> dict:
        if not IDENTIFIER.fullmatch(checkpoint_id): raise RegistryError('bad_checkpoint_id')
        rec = self._read(self.root / 'checkpoints' / f'{checkpoint_id}.json')
        if rec is None: raise RegistryError('unknown_checkpoint')
        return rec

    def activate(self, checkpoint_id: str, *, available_models: set[str] | None = None) -> dict:
        """Activate arbitrary-depth verified checkpoint, but only when known offline.

        The callback must inspect a trusted local session controller; remote UI
        clients/LLM responses must never toggle it. Model availability is explicit.
        """
        with self.transaction():
            self._audit_entries()
            if self.safe_to_switch() is not True: raise UnsafeSwitch('active_or_unknown_session')
            cp = self.get_checkpoint(checkpoint_id)
            if cp['status'] != 'verified': raise RegistryError('unverified_checkpoint')
            if not self.lab_mode and cp.get('scope') != 'integration':
                raise RegistryError('checkpoint_not_qualified_for_production')
            evidence_path = self.root / 'blobs' / cp['test_report_hash']
            if not evidence_path.is_file() or digest(evidence_path.read_bytes()) != cp['test_report_hash']:
                raise RegistryError('test_report_missing_or_modified')
            release = self.get_release(cp['release_id'])
            if cp.get('release_hash') != digest(encode(release)):
                raise RegistryError('release_manifest_modified')
            self.verify_release(release)
            if release['external_model'] and (available_models is None or release['external_model'] not in available_models):
                raise CompatibilityError('external_model_not_verified_available')
            active = {'checkpoint_id': cp['id'], 'release_id': release['id'],
                      'activated_utc': utc_now(), 'release_hash': digest(encode(release))}
            self._atomic(self.root / 'active.json', encode(active))
            self._append_audit('checkpoint_activated', {'id': checkpoint_id, 'release_id': release['id']})
            return active

    def status(self) -> dict:
        with self.transaction():
            active = self._read(self.root / 'active.json')
            points = sorted(p.stem for p in (self.root / 'checkpoints').glob('*.json'))
            return {'active': active, 'checkpoints': points, 'artifact_count': len(self._read(self.root / 'artifacts.json', {})),
                    'audit': self.verify_audit()}

    def draft_module_rollback(self, checkpoint_id: str, component: str, version: str,
                              new_release_id: str) -> dict:
        """Draft only: never activates untested component combinations."""
        if not COMPONENT.fullmatch(component) or not VERSION.fullmatch(version):
            raise RegistryError('invalid_module_rollback')
        with self.transaction():
            checkpoint = self.get_checkpoint(checkpoint_id)
            release = self.get_release(checkpoint['release_id'])
            if component not in release['components']:
                raise CompatibilityError('component_not_in_release')
            replacement = dict(release['components'])
            replacement[component] = version
            return self.create_release(new_release_id, replacement,
                                       contract_major=release['contract_major'],
                                       description=f'Draft: {component} => {version} from {checkpoint_id}',
                                       external_model=release['external_model'])
