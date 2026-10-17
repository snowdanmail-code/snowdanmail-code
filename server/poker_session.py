"""Conservative per-device spend counter. Does not guarantee monetary safety."""
import threading
import time

class PokerBudget:
    def __init__(self, clock=time.monotonic):
        self.lock=threading.Lock(); self.clock=clock; self.sessions={}

    def reserve(self, session_id, seq, action, cost, max_actions=20, max_chips=0):
        with self.lock:
            # RAM-only reservations; budget charged on issued command even if gesture fails.
            now=self.clock()
            old=self.sessions.get(session_id)
            if old is None:
                if len(self.sessions)>=16: raise ValueError('too_many_sessions')
                old={'seq':-1,'steps':0,'used':0.0,'at':now,'last_action':None,'last_action_at':-1e10}
                self.sessions[session_id]=old
            if seq<=old['seq']: raise ValueError('replayed_frame')
            if now-old['at']>600 and old['steps']>0: raise ValueError('session_expired')
            if old['steps']>=max_actions: raise ValueError('action_limit')
            if old['used']+cost>max_chips: raise ValueError('budget_limit')
            # Prevent accidental repeated wagers/actions from near-identical frames.
            if action!='wait' and action==old['last_action'] and now-old['last_action_at']<8:
                raise ValueError('duplicate_action_cooldown')
            old['seq']=seq; old['at']=now
            if action!='wait':
                old['used']+=cost;old['steps']+=1
                old['last_action']=action;old['last_action_at']=now
            return {'issued_actions':old['steps'],'charged_chips':old['used']}

    def reset(self):
        with self.lock: self.sessions.clear()
