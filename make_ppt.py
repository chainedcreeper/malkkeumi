# 출품용 PPT 생성 — 흑백, 3장(표지 / 어떤 프로그램 / 구조도). python make_ppt.py
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

BLACK = RGBColor(0, 0, 0)
WHITE = RGBColor(255, 255, 255)
GRAY = RGBColor(245, 245, 245)
FONT = '맑은 고딕'

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def box(slide, x, y, w, h, text, size=14, bold=False, fill=WHITE, align=PP_ALIGN.CENTER, line=True):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = fill
    s.line.color.rgb = BLACK; s.line.width = Pt(1.2 if line else 0)
    if not line: s.line.fill.background()
    tf = s.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Emu(50000); tf.margin_top = tf.margin_bottom = Emu(30000)
    for i, ln in enumerate(text.split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = ln; p.alignment = align
        for r in p.runs: r.font.name = FONT; r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = BLACK
    return s


def label(slide, x, y, w, text, size=14, bold=False, align=PP_ALIGN.LEFT):
    t = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(0.5))
    tf = t.text_frame; tf.word_wrap = True
    for i, ln in enumerate(text.split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = ln; p.alignment = align
        for r in p.runs: r.font.name = FONT; r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = BLACK
    return t


def arrow(slide, x1, y1, x2, y2):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = BLACK; c.line.width = Pt(1.5)
    # 화살촉
    c.line._get_or_add_ln().append(__import__('pptx').oxml.parse_xml(
        '<a:tailEnd type="triangle" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>'))


# ── 1. 표지 ──
s = prs.slides.add_slide(BLANK)
label(s, 1.2, 2.6, 11, '말끔이', 60, True)
label(s, 1.25, 3.9, 11, '내 컴퓨터 청소 매니저  —  캐시 · 광고 · 안 쓰는 것', 20)
label(s, 1.25, 6.6, 11, '"크고 복잡한 것 말고, 작지만 정교한 것"', 14)

# ── 2. 어떤 프로그램인가 ──
s = prs.slides.add_slide(BLANK)
label(s, 0.9, 0.55, 11, '어떤 프로그램인가', 30, True)
lines = [
    ('앱별 캐시 관리', '캐시 쓰는 앱을 자동 서치로 찾아 등록하고, 임계치를 넘으면 청소'),
    ('절대 바로 지우지 않음', '미리보기 → 사용자 승인 → 휴지통 경유 · 분리는 보관함으로(되돌리기 지원)'),
    ('광고 점검 · 차단', '유입 4경로(자동실행·스케줄러·확장·알림) 스캔 + hosts 기반 시스템 전체 차단'),
    ('일반인용 상태 화면', '숫자 대신 "지금 컴퓨터가 왜 느린지" 한 문장으로'),
    ('상주 없음 · 자동 업데이트', '주기 청소는 윈도우 스케줄러에 위임, 새 버전은 GitHub 에서'),
]
y = 1.7
for t, d in lines:
    label(s, 1.1, y, 3.4, t, 17, True)
    label(s, 4.7, y, 7.6, d, 15)
    y += 1.05

# ── 3. 구조도 ──
s = prs.slides.add_slide(BLANK)
label(s, 0.9, 0.4, 11, '구조', 30, True)
CX = 6.667   # 가로 중심
# 화면
box(s, 2.9, 1.15, 7.5, 0.72, '화면 (HTML · JS)   —   상태 · 캐시 · 광고 · 안 쓰는 것 · 중복 · 디스크 · 자동청소', 13, True)
arrow(s, CX, 1.87, CX, 2.17)
# 브리지
box(s, 4.4, 2.17, 4.5, 0.6, 'Api 브리지 (app.py)', 13, True)
arrow(s, CX, 2.77, CX, 3.07)
# 코어 8모듈 (2행 x 4열) — 오른쪽 GitHub 상자(x=11.15~)와 겹치지 않게 x0+폭 합계를 10.6 이내로
mods = [('상태 진단', 'sysinfo'), ('캐시 등록부', 'cache_registry'), ('안전 삭제', 'cleaner'), ('광고 스캔', 'adscan'),
        ('hosts 차단', 'adblock'), ('안 쓰는 것', 'unused'), ('중복 파일', 'dupes'), ('디스크 지도', 'diskmap')]
x0, y0, w, h, gx, gy = 1.7, 3.07, 2.1, 0.78, 0.12, 0.14
for i, (k, m) in enumerate(mods):
    box(s, x0 + (i % 4) * (w + gx), y0 + (i // 4) * (h + gy), w, h, f'{k}\n{m}.py', 11.5, fill=GRAY)
arrow(s, CX, y0 + 2 * h + gy, CX, y0 + 2 * h + gy + 0.3)
# 시스템 층 (코어 그리드와 좌우 정렬)
box(s, 1.7, 5.15, 8.76, 0.72, '윈도우 시스템   —   파일 · 휴지통  |  레지스트리  |  hosts  |  작업 스케줄러', 13)
# 깃허브 (옆, 코어 그리드 오른쪽 끝 10.46 과 띄움)
box(s, 11.15, 2.17, 1.85, 1.68, 'GitHub\n(updater.py)\n버전 비교\n→ 갱신', 11, fill=GRAY)
arrow(s, 11.15, 2.6, 8.95, 2.5)
label(s, 2.0, 6.3, 10, '배포: PyInstaller 단일 폴더 exe (파이썬 설치 불필요)  ·  데이터는 exe 옆 data/ 에만 기록', 12.5)

OUT = '말끔이_발표.pptx'
prs.save(OUT)
print('saved', OUT)
