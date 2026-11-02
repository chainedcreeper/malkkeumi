# 출품용 PPT 생성 — 흑백·간결 4장: 표지 / 언어·기술 / 완성된 기능 / 구조. python make_ppt.py
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
    s.line.color.rgb = BLACK; s.line.width = Pt(1.2)
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
    c.line._get_or_add_ln().append(__import__('pptx').oxml.parse_xml(
        '<a:tailEnd type="triangle" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>'))


# ── 1. 표지 ──
s = prs.slides.add_slide(BLANK)
label(s, 1.2, 2.6, 11, '말끔이', 60, True)
label(s, 1.25, 3.9, 11, '내 컴퓨터 청소 매니저  —  상태 · 캐시 · 광고 · 악성 · 파일 정리', 20)
label(s, 1.25, 6.6, 11, '"크고 복잡한 것 말고, 작지만 정교한 것"', 14)

# ── 2. 어떤 언어·기술로 만들었나 ──
s = prs.slides.add_slide(BLANK)
label(s, 0.9, 0.55, 11, '어떤 언어 · 기술로 만들었나', 30, True)
rows = [
    ('언어', 'Python 3.12 (본체 로직)  +  HTML · CSS · JavaScript (화면)'),
    ('화면 기술', 'pywebview — 윈도우 내장 WebView2 엔진을 빌려 쓰는 경량 데스크톱 UI (Electron 대비 1/10 크기)'),
    ('시스템 연동', 'psutil(프로세스·자원) · 레지스트리(winreg) · hosts 파일 · 작업 스케줄러 · 휴지통 셸 API · Authenticode 서명 검증'),
    ('탐지 기술', 'SHA-256 3단 중복 판별 · 공개 악성 해시 DB(MalwareBazaar) 조회 · Prefetch 실행 기록 분석 · Zone.Identifier 출처 추적'),
    ('배포 체계', 'PyInstaller 단일 exe 런처(15MB, 무설치) — 실행 때마다 GitHub 의 코드와 버전 비교 → 자동 업데이트'),
]
y = 1.7
for t, d in rows:
    label(s, 1.1, y, 2.6, t, 16, True)
    label(s, 3.9, y, 8.6, d, 14)
    y += 1.02

# ── 3. 완성된 기능 ──
s = prs.slides.add_slide(BLANK)
label(s, 0.9, 0.55, 11, '완성된 기능', 30, True)
feats = [
    ('컴퓨터 상태', '작업관리자 대체 — CPU·RAM·GPU·온도, 부하 순위 + 프로그램 종료, 모서리 미니 위젯'),
    ('캐시 청소', '앱별 등록부 + 자동 서치로 캐시 쓰는 앱 발굴, 기준(임계치) 초과분 원클릭 청소'),
    ('광고 점검·차단', '유입 4경로 스캔 + hosts 기반 시스템 전체 차단(자동 백업·원클릭 해제·작동 자가진단)'),
    ('악성 점검', '자동실행·임시폴더 실행파일의 서명·위치·위장 신호 + 악성 해시 DB 조회 + Defender 연동'),
    ('파일 정리', '안 쓰는 덩어리 탐지·보관함 분리 / 파일 해석("설치 끝났으면 지워도 돼요") / 중복 파일 3단 판별'),
    ('디스크 지도', '폴더 트리를 한 계층씩 즉시 측정 — 클릭 탐색기 이동 · 우클릭 경로 복사'),
    ('자동화', '작업 스케줄러 등록(상주 없음) — 매일 자동 청소 + 완료 토스트 알림 + 부팅 시 업데이트 확인'),
]
y = 1.55
for t, d in feats:
    label(s, 1.1, y, 2.6, t, 15.5, True)
    label(s, 3.9, y, 8.6, d, 13.5)
    y += 0.78
label(s, 1.1, y + 0.1, 11, '원칙: 어떤 파일도 바로 지우지 않는다 — 미리보기 → 승인 → 휴지통, 모든 긴 작업은 % 진행 표시', 13, True)

# ── 4. 구조 ──
s = prs.slides.add_slide(BLANK)
label(s, 0.9, 0.4, 11, '구조', 30, True)
CX = 6.667
box(s, 2.9, 1.15, 7.5, 0.72, '화면 (HTML · JS)  —  상태 · 캐시 · 광고 · 악성 · 안쓰는것 · 파일 · 중복 · 디스크 · 자동청소', 12, True)
arrow(s, CX, 1.87, CX, 2.17)
box(s, 4.4, 2.17, 4.5, 0.6, 'Api 브리지 (app.py)', 13, True)
arrow(s, CX, 2.77, CX, 3.07)
mods = [('상태·위젯', 'sysinfo'), ('캐시 등록부', 'cache_registry'), ('안전 삭제', 'cleaner'), ('광고 스캔', 'adscan'),
        ('hosts 차단', 'adblock'), ('악성 점검', 'malscan'), ('파일·중복', 'unused · dupes'), ('디스크 지도', 'diskmap')]
x0, y0, w, h, gx, gy = 1.7, 3.07, 2.1, 0.78, 0.12, 0.14
for i, (k, m) in enumerate(mods):
    box(s, x0 + (i % 4) * (w + gx), y0 + (i // 4) * (h + gy), w, h, f'{k}\n{m}.py', 11, fill=GRAY)
arrow(s, CX, y0 + 2 * h + gy, CX, y0 + 2 * h + gy + 0.3)
box(s, 1.7, 5.15, 8.76, 0.72, '윈도우 시스템  —  파일 · 휴지통 | 레지스트리 | hosts | 작업 스케줄러 | Defender', 12.5)
box(s, 11.15, 2.17, 1.85, 1.9, '런처 exe\n↕\nGitHub\n버전 비교\n→ 코드 교체', 10.5, fill=GRAY)
arrow(s, 11.15, 2.6, 8.95, 2.5)
label(s, 1.7, 6.3, 10.5, '배포: 무설치 단일 exe — 폴더엔 exe 하나, 코드는 GitHub 가 정본 · 켤 때마다 자동 최신화 (오프라인이면 그대로 실행)', 12.5)

OUT = '말끔이_발표.pptx'
prs.save(OUT)
print('saved', OUT)
