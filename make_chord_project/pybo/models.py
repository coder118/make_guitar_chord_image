from pybo import db #init 파일에 선언을 해둬서 거기서 만든 db를 사용
import json
from datetime import datetime


class GuitarCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(255), unique=True, nullable=False)
    chord_type = db.Column(db.String(50), nullable=True)#코드 종류 (major, minor, 7th 등)
    coordinates = db.Column(db.Text, nullable=False)  # 좌표값을 그대로 저장
    mute = db.Column(db.String(255))  # mute 정보 저장
    usage_count = db.Column(db.Integer, default=0)#사용 빈도 (통계 목적)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def coordinates_list(self):
        return json.loads(self.coordinates)

    @coordinates_list.setter
    def coordinates_list(self, value):
        self.coordinates = json.dumps(value)

    @property
    def mute_list(self):
        return json.loads(self.mute) if self.mute else []

    @mute_list.setter
    def mute_list(self, value):
        self.mute = json.dumps(value) if value else None
    
    
