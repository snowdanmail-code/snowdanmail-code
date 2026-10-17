"""Read-only resolution of runtime policies from a verified release registry.

No dynamic imports, eval, or executable plug-ins. Payloads are restricted JSON
and identified by their content hashes. Switching remains an offline process
through arc_versions; requests cannot activate a build.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
from arc_versions.registry import VersionRegistry, RegistryError, digest, encode


class RuntimeUntrusted(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeSnapshot:
    release_id: str
    checkpoint_id: str
    policy_version: str
    policy: dict[str, Any]
    is_lab: bool
    release_sha256: str


def validate_policy(p: dict) -> dict:
    required = {'schema', 'name', 'min_confidence', 'stable_frames', 'allowed_game',
                'allow_replay_analysis', 'allow_money_actions', 'unknown_action',
                'min_seated_players', 'frame_max_age_ms'}
    if not isinstance(p, dict) or set(p) != required or p['schema'] != 'arc.runtime_policy.v1':
        raise RuntimeUntrusted('invalid_policy_schema')
    if not isinstance(p['name'], str) or not 1 <= len(p['name']) <= 64:
        raise RuntimeUntrusted('invalid_policy_name')
    if type(p['min_confidence']) not in (float,int) or not .50 <= p['min_confidence'] <= 1:
        raise RuntimeUntrusted('invalid_confidence')
    if type(p['stable_frames']) is not int or not 2 <= p['stable_frames'] <= 6:
        raise RuntimeUntrusted('invalid_stable_frames')
    if p['allowed_game'] != 'holdem_nl' or p['allow_money_actions'] is not False:
        raise RuntimeUntrusted('unsafe_policy')
    if p['allow_replay_analysis'] is not False or p['unknown_action'] != 'hold':
        raise RuntimeUntrusted('unsafe_replay_or_unknown_policy')
    if type(p['min_seated_players']) is not int or p['min_seated_players'] != 3:
        raise RuntimeUntrusted('invalid_seating_policy')
    if type(p['frame_max_age_ms']) is not int or not 200 <= p['frame_max_age_ms'] <= 3000:
        raise RuntimeUntrusted('invalid_frame_age')
    return p


class ReleaseReader:
    def __init__(self, path: str | Path, *, allow_lab: bool=False):
        self.root = Path(path)
        self.allow_lab = allow_lab

    def resolve(self) -> RuntimeSnapshot:
        # Always re-open under registry transaction: no long-lived cached active
        # record that survives an offline switch.
        registry = VersionRegistry(self.root)
        with registry.transaction():
            registry.verify_audit()
            active = registry._read(self.root / 'active.json')
            if not isinstance(active,dict):
                raise RuntimeUntrusted('no_active_checkpoint')
            cp = registry.get_checkpoint(active.get('checkpoint_id',''))
            rel = registry.get_release(cp['release_id'])
            if (active.get('release_id') != rel['id'] or active.get('release_hash') != digest(encode(rel))
                or cp['release_hash'] != digest(encode(rel)) or cp['status']!='verified'):
                raise RuntimeUntrusted('checkpoint_mismatch')
            if cp['scope'] != 'integration' and not self.allow_lab:
                raise RuntimeUntrusted('lab_checkpoint_blocked')
            report = self.root / 'blobs' / cp['test_report_hash']
            if not report.is_file() or digest(report.read_bytes()) != cp['test_report_hash']:
                raise RuntimeUntrusted('missing_test_evidence')
            registry.verify_release(rel)
            version = rel['components'].get('runtime_policy')
            if not version:
                raise RuntimeUntrusted('runtime_policy_not_registered')
            record = registry._read(self.root / 'artifacts.json',{}).get(f'runtime_policy@{version}')
            if record is None:
                raise RuntimeUntrusted('runtime_policy_missing')
            blob = (self.root / 'blobs' / record['sha256']).read_bytes()
            if digest(blob) != record['sha256'] or len(blob)>16000:
                raise RuntimeUntrusted('runtime_policy_corrupt')
            try:
                policy = validate_policy(json.loads(blob))
            except (ValueError, UnicodeError) as e:
                raise RuntimeUntrusted('runtime_policy_invalid') from e
            return RuntimeSnapshot(rel['id'],cp['id'],version,policy,
                                   cp['scope']!='integration',digest(encode(rel)))


def standard_policy(name: str='baseline', min_confidence:float=.82,
                    stable_frames:int=2) -> dict:
    return validate_policy({'schema':'arc.runtime_policy.v1', 'name':name,
        'min_confidence':min_confidence, 'stable_frames':stable_frames,
        'allowed_game':'holdem_nl','allow_replay_analysis':False,
        'allow_money_actions':False,'unknown_action':'hold',
        'min_seated_players':3, 'frame_max_age_ms':1200})
