"""경로 중앙화 — 소스 실행과 PyInstaller exe 실행 양쪽에서 맞는 위치.

exe(frozen)일 때 __file__ 은 임시 압축해제 폴더(_MEIPASS)를 가리켜서, 데이터를 거기 적으면
재부팅마다 사라진다. 데이터(등록부·이력·백업)는 항상 'exe 가 있는 폴더' 기준이어야 한다.
- APP_DIR: 프로그램 폴더 (exe 위치 / 소스면 프로젝트 루트) — data/, VERSION 이 여기
- RES_DIR: 읽기 전용 리소스 (ui/) — exe 면 번들 내부(_MEIPASS), 소스면 APP_DIR 와 같음
"""
import os
import sys

FROZEN = getattr(sys, 'frozen', False)
APP_DIR = os.path.dirname(sys.executable) if FROZEN \
    else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES_DIR = getattr(sys, '_MEIPASS', APP_DIR)
DATA = os.path.join(APP_DIR, 'data')
