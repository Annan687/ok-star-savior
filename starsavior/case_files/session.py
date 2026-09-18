"""Optional repeated rounds. Every round owns fresh state, logs and search process."""
from .solver import Runner,Control

class Session:
    def __init__(self,event,report,engine='native',auto_restart=False,runner_factory=Runner):
        self.control=Control(event);self.event=event;self.report=report;self.engine=engine
        self.auto_restart=bool(auto_restart);self.runner_factory=runner_factory
        self.round_number=0;self.best=None;self.completed=0
    def on_report(self,event):
        data={**event,'round':self.round_number,'continuous':self.auto_restart}
        if event.get('finished'):
            self.completed+=1
            score=event.get('final_score')
            if score is not None:self.best=score if self.best is None else max(self.best,score)
            if self.auto_restart:
                data['status']='第 '+str(self.round_number)+' 局已結算，2 秒後自動重開。'
        data.update(session_best=self.best,completed_rounds=self.completed)
        self.report(data)
    def run(self):
        game=None
        while True:
            self.control.check();self.round_number+=1
            runner=self.runner_factory(self.event,self.on_report,engine=self.engine,existing_game=game,
                start_screen=('result' if game is not None else 'home_or_result') if self.auto_restart else 'home')
            self.on_report({'status':'準備第 '+str(self.round_number)+' 局…','round_started':True,'points':0,'moves':0})
            outcome=runner.run()  # Errors/cancellation propagate; never restart a failed round.
            if outcome!='result' or not self.auto_restart:return outcome
            game=runner.game
            # Interruptible inter-round delay, with foreground/geometry checks throughout.
            for _ in range(20):
                self.control.check();game.check();self.control.wait(.1)
