"""Local checkpoints for an interrupted home run, isolated from schedules."""
import hashlib
import json
from datetime import date
from pathlib import Path
from .activity import CURRENT_EVENT_NAME
from .policy import NeedsReview

PATH = Path('runs/home-progress.json')


def signature(config):
    values = {key: config.get(key, '略過') for key in
              ('體力刷關', '限時據點關卡', '激戰委託關卡')}
    values['執行項目'] = sorted(set(config['執行項目']))
    values['活動'] = CURRENT_EVENT_NAME
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class HomeProgress:
    def __init__(self, config, path=None, today=None):
        self.path = Path(path) if path is not None else PATH
        self.day = today or date.today().isoformat()
        self.signature = signature(config)
        self.selected = set(config['執行項目'])
        self.data = None

    def load(self):
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema') != 1:
                raise ValueError('schema')
            if (data.get('day') != self.day or data.get('scope') != 'home'
                    or data.get('signature') != self.signature or data.get('finished') is True):
                return None
            if (data.get('finished') is not False or not isinstance(data.get('done'), dict)
                    or set(data['done']) - self.selected
                    or any(not isinstance(v, str) for v in data['done'].values())
                    or data.get('current') not in self.selected | {None}
                    or not isinstance(data.get('detail'), str)):
                raise ValueError('checkpoint')
            return data
        except (OSError, ValueError, TypeError) as error:
            raise NeedsReview('續跑紀錄無法讀取；請檢查紀錄，或按「重新開始」跑新一輪') from error

    def begin(self, resume=True, scope='home'):
        old = self.load() if resume and scope == 'home' else None
        self.data = dict(schema=1, day=self.day, signature=self.signature, scope=scope,
                         done=dict(old['done']) if old else {}, current=None,
                         detail='', finished=False)
        self.save()
        return self.data['done'].copy()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.path)

    def before(self, name):
        self.data.update(current=name, detail='上次執行中斷，按開始日課可重試此項')
        self.save()

    def completed(self, name, detail):
        self.data['done'][name] = str(detail)
        self.data.update(current=None, detail='')
        self.save()

    def interrupted(self, detail):
        self.data['detail'] = str(detail)
        self.save()

    def finish(self):
        self.data.update(finished=True, current=None, detail='')
        self.save()

    def info(self):
        data = self.load()
        if data is None:
            return {}
        info = {name: '已執行：前輪已完成；'+detail for name, detail in data['done'].items()}
        if data['current']:
            info[data['current']] = '需校正／尚未完成：'+data['detail']
        info['執行狀態'] = '可接續上輪日課'
        return info
