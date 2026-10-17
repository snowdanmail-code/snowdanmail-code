"""Read-only state service binding immutable release profiles to observers."""
from __future__ import annotations
from .release import ReleaseReader, RuntimeUntrusted
from .observe import Observer
import threading

class ObserverService:
    def __init__(self, registry_path, *, allow_lab=False):
        self.reader=ReleaseReader(registry_path,allow_lab=allow_lab)
        self._snapshot=None
        self._observer=None
        self._lock=threading.RLock()

    def _refresh(self):
        snap=self.reader.resolve()  # full hash/audit check on every request
        if self._snapshot is None or self._snapshot.release_sha256!=snap.release_sha256:
            self._snapshot=snap
            self._observer=Observer(snap.policy)
        return snap

    def _public_status(self,snap):
        return {'enabled':True,'checkpoint':snap.checkpoint_id,'release':snap.release_id,
                'policy_version':snap.policy_version,'policy_name':snap.policy['name'],
                'lab_only':snap.is_lab,'money_actions_enabled':False,
                'autonomous_betting_enabled':False}

    def status(self):
        with self._lock:
            return self._public_status(self._refresh())

    def observe(self,session,scene):
        with self._lock:
            snap=self._refresh()
            return {'runtime':self._public_status(snap),
                    'observation':self._observer.evaluate(session,scene)}
