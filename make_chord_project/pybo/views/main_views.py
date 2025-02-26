from flask import Blueprint,send_file
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

import os
import google.generativeai as genai
from flask import request, jsonify
from dotenv import load_dotenv


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


@bp.route('/')
def index():
    return 'Pybo index'

import re

def parse_gpt_response(gpt_response):
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
def create_fretboard():
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
    
        
    # X 표시 추가 (맨 아래 선 왼쪽)
    # draw.line((30, 480, 50, 520), fill='black', width=2)
    # draw.line((30, 520, 50, 480), fill='black', width=2)
    
    # # "3fr" 텍스트 추가 (맨 위 선 위)
    # font = ImageFont.truetype("arial.ttf", 20)  # 폰트 파일 경로와 크기 지정
    # draw.text((100, 70), "3fr", fill='black', font=font)
    
     
    coordinates = create_coordinate_system()
    
    gpt_response = """(1,1)/(1,2)/(1,3)/(1,4)/(1,5)/(1,6)
(3,3)
(3,5)
(2,4)
mute:없음"""
    
    points_to_draw ,mute, first_x= parse_gpt_response(gpt_response)
    
    fret_text = f"{first_x}f" if first_x > 2 else "1f"
    font = ImageFont.truetype("arial.ttf", 20)
    draw.text((90, 30), fret_text, fill='black', font=font)
    
    
    # 파싱된 좌표에 점 찍기
    for fret, string in points_to_draw:
        if (fret, string) in coordinates:
            x, y = coordinates[(fret, string)]
            circle_radius = 20  # 원 크기 증가
            draw.ellipse((x-circle_radius, y-circle_radius-40, x+circle_radius, y+circle_radius-40), fill='black')
    
     # Mute된 줄에 X 표시 그리기
    for string in mute:
        y = 100 + (string - 1) * 80
        draw.line((30, y-10, 50, y+10), fill='red', width=2)
        draw.line((30, y+10, 50, y-10), fill='red', width=2)
    
    #플라스크에서 이미지를 만들수 없어서 사용
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    #generate_text()
    
    return send_file(img_io, mimetype='image/png')