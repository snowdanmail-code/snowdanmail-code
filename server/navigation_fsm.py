"""Fail-closed state-transition checker for observed screens, not a clicker.

The agent must not transition by wishful thinking. A detected screen is validated
against possible UI state changes; unexpected transitions require a fresh image.
"""

ALLOWED = {
 'cash_lobby': {'cash_lobby', 'buyin_dialog', 'table_waiting', 'unknown'},
 'buyin_dialog': {'buyin_dialog', 'cash_lobby', 'table_waiting', 'unknown'},
 'table_waiting': {'table_waiting', 'table_playing', 'action_controls', 'showdown', 'cash_lobby', 'unknown'},
 'table_playing': {'table_playing', 'table_waiting', 'action_controls', 'raise_panel', 'showdown', 'cash_lobby', 'unknown'},
 'action_controls': {'action_controls', 'raise_panel', 'table_playing', 'table_waiting', 'showdown', 'unknown'},
 'raise_panel': {'raise_panel', 'action_controls', 'table_playing', 'unknown'},
 'showdown': {'showdown', 'table_waiting', 'table_playing', 'cash_lobby', 'unknown'},
 'unknown': {'cash_lobby', 'buyin_dialog', 'table_waiting', 'table_playing',
             'action_controls', 'raise_panel', 'showdown', 'unknown'},
}

class NavigationTracker:
    def __init__(self):
        self.state='unknown'
        self.history=[]

    def observe(self, screen, confidence):
        if screen not in ALLOWED or type(confidence) not in (float,int) or not 0<=confidence<=1:
            raise ValueError('bad_observation')
        if confidence<.90 or screen=='unknown':
            self.state='unknown'
            self.history.append('unknown')
            return {'accepted':False,'reason':'uncertain','state':'unknown'}
        if screen not in ALLOWED[self.state]:
            self.state='unknown'
            self.history.append('unknown')
            return {'accepted':False,'reason':'unexpected_transition','state':'unknown'}
        self.state=screen
        self.history.append(screen)
        self.history=self.history[-30:]
        return {'accepted':True,'reason':'recognized','state':screen}
