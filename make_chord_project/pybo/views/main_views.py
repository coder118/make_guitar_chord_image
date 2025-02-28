from flask import Blueprint,send_file
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

import os
import google.generativeai as genai
from flask import request, jsonify,render_template
from dotenv import load_dotenv
from pybo.models import GuitarCode
from pybo import db
import json


bp = Blueprint('main', __name__, url_prefix='/')


def generate_text():
    load_dotenv() # .env 파일 로드
    api_key = os.getenv("GEMINI_API_KEY") # 환경 변수에서 API 키 가져오기

    if not api_key:
        print("API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    system_instruction="""기타 코드 운지법에 대해 질문을 하면 어떤 말을 할 필요도 없다. 오로지 좌표값으로만 출력을 해줘야 한다. 예를 들어 G코드 운지법에 대해 물어보면 2번프랫의 5번줄을 잡으니까 (2,5)이렇게 적고 프랫이 바뀔때만 /n로 줄바꿈을 해준다. 
    프랫이 바뀌지 않을 경우 (1,2)/(1,3)/(1,4) 이런식으로 /(슬래쉬)를 사용해서 구분한다. 마지막으로 뮤트할 줄이 존재한다면 맨 마지막 줄에 mute: 이런식으로 적고 뮤트되어야 할 줄을 숫자로 입력해준다. 만약 존재하지 않는다면 없음이라는 단어를 출력하면된다. 똑같은 질문을 반복하더라도 정확하게 기타 코드의 운지법을 알려줘야 한다. """
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash',system_instruction=system_instruction)
    response = model.generate_content("f코드 운지법")
    print(response.text)


@bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        code = request.form['code']
        return create_fretboard(code)
    return render_template('index.html')

import re

def parse_gpt_response(gpt_response): #ai가 알려준 좌표값을 분류하는 함수
    coordinates = []
    mute = []
    first_x = None #들어오는 첫 좌표값이 2를 넘어가게 되면 이미지 범위를 초과할 경우를 예상해서 첫번쨰 좌표값을 저장한다. 
    lines = gpt_response.split('\n')
    for line in lines:
        if '(' in line and ')' in line:
            # 정규표현식을 사용하여 모든 (x,y) 형태의 좌표를 찾습니다.
            coords = re.findall(r'\((\d+),(\d+)\)', line)
            for x, y in coords:
                x, y = int(x), int(y)
                if first_x is None:
                    first_x = x
                if first_x > 2: #3번 프렛을 넘어가게 되면 뒤에 그림이 잘릴 수도 있기때문에 넘어가지 않게 새로운 좌표값으로 변경을 해준다. 그리고 줄 아래에 프랫을 표시함으로써 문제를 해결해준다 
                    new_x = x - first_x + 1#3이 넘어가는 좌표가 있으면 firstx에 저장된 값을 빼주고 1을 더해주면 원래의 좌표 모양을 나타낼 수 있다. 
                else:
                    new_x = x
                coordinates.append((new_x, y))
                #coordinates.append((int(x), int(y)))
        elif line.startswith('mute:'):
            mute_part = line.split(':', 1)[1].strip()
            if mute_part.lower() != '없음':
                mute_values = re.findall(r'\d+', mute_part)
                mute = [int(v) for v in mute_values]
            
    return coordinates,mute, first_x

def create_coordinate_system():
    coordinates = {}
    for string in range(1, 7):  # 6개의 가로 공간
        for fret in range(1, 7):  # 6개의 세로 공간
            x = 50 + (fret * 100) - 50  # 세로선 사이의 중간 지점
            y = 100 + (string * 80) - 40  # 가로선 위의 지점
            coordinates[(fret, string)] = (x, y)
    return coordinates

@bp.route('/line')
def create_fretboard(code=None):
    
    if code is None:
        code = request.args.get('code')
    
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # 6개의 가로선 그리기 (아래에서 위로 두께 감소)
    for i in range(6):
        thickness = i 
        y = 100 + i * 80
        draw.line((50, y, 550, y), fill='black', width=thickness)
    
    # 14개의 세로선 그리기
    for i in range(6):
        x = 50 + i * 100
        draw.line((x, 100, x, 500), fill='black', width=1)
    
 
    coordinates = create_coordinate_system()
    
    gpt_response = """(2,1)/(2,2)/(2,3)/(2,4)/(2,5)/(2,6)
(4,2)
(4,3)
(4,4)
mute:없음"""
    
    
    
    # 데이터베이스에서 코드 검색
    existing_code = GuitarCode.query.filter_by(code=code).first()
    
    if existing_code:
        points_to_draw = existing_code.coordinates
        mute = existing_code.mute
        first_x = int(points_to_draw[2])
        points_to_draw = json.loads(points_to_draw)
        print("db에 있는 값입니다.")
    else:
        # GPT API를 사용하여 새로운 좌표 생성
        points_to_draw, mute,first_x = parse_gpt_response(gpt_response) #원래는 parse_gpt_response(generate_text())를 넣어서 바로 ai가 검색할 수 있게 해야 함
        
        # 새로운 코드를 데이터베이스에 저장
        new_code = GuitarCode(code=code)
        new_code.coordinates_list = points_to_draw # 파이썬의 리스트 형태로 sqlite에 넣을 수 가 없어서 json형태를 사용
        new_code.mute_list = mute
        db.session.add(new_code)
        db.session.commit()
    
    
    
    
    
    
    
    #points_to_draw ,mute, first_x= parse_gpt_response(gpt_response)
    
    fret_text = f"{first_x}f" if first_x > 2 else "1f"#총 이미지로 표현할 수 있는 이미지가 5줄. 첫번째 잡는 좌표값이 3플랫이면 이미지 범위를 초과할 경우가 생길것을 방지해서 2가 넘어가면 줄 아래에 플랫의 번호를 적게 시킴
    font = ImageFont.truetype("arial.ttf", 20)
    draw.text((90, 30), fret_text, fill='black', font=font)
    
    
    # 파싱된 좌표에 점 찍기
    for fret, string in points_to_draw:
        if (fret, string) in coordinates:
            x, y = coordinates[(fret, string)]
            circle_radius = 20  # 원 크기 증가
            draw.ellipse((x-circle_radius, y-circle_radius-40, x+circle_radius, y+circle_radius-40), fill='black')
    
     # Mute된 줄에 X 표시 그리기
    if mute is not None and mute: # mute가 none 값으로 잡히는 경우가 있다. 
        for string in mute:
            y = 100 + (string - 1) * 80
            draw.line((30, y-10, 50, y+10), fill='red', width=2)
            draw.line((30, y+10, 50, y-10), fill='red', width=2)
        
    #플라스크에서 이미지를 만들수 없어서 사용
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    #generate_text() #api 이용하는 코드
    
    return send_file(img_io, mimetype='image/png')





#https://rominlamp.tistory.com/22      -- env파일과 관련된 정보

# from pybo.models import GuitarCode  
# >>> print(GuitarCode.__table__) 
# guitar_code
# >>> print(GuitarCode.__table__.columns) flask shell에서 db 테이블 속성 정보 확인 법