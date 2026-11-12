from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT = Path('/Users/minseojang/Documents/ChatGPT/final-project/output/erd/ProPitch_ERD_v8_분석_내용평가.png')
OUT.parent.mkdir(parents=True, exist_ok=True)
FONT = '/System/Library/Fonts/Supplemental/AppleGothic.ttf'
title_font = ImageFont.truetype(FONT, 34)
sub_font = ImageFont.truetype(FONT, 24)
card_font = ImageFont.truetype(FONT, 24)
field_font = ImageFont.truetype(FONT, 19)
small_font = ImageFont.truetype(FONT, 17)

im = Image.new('RGB', (1900, 1400), '#F9FAFC')
d = ImageDraw.Draw(im)


def label(x, y, value):
    box = d.textbbox((0, 0), value, font=small_font)
    width = box[2] + 18
    d.rounded_rectangle((x - width / 2, y - 15, x + width / 2, y + 15), radius=7, fill='#FFFFFF', outline='#C9D4E0')
    d.text((x - box[2] / 2, y - box[3] / 2 - 1), value, font=small_font, fill='#496079')


def line(points, dash=False, color='#8EA1B5', width=3):
    if not dash:
        d.line(points, fill=color, width=width, joint='curve')
        return
    for a, b in zip(points, points[1:]):
        x1, y1 = a
        x2, y2 = b
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if not length:
            continue
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        at = 0
        while at < length:
            end = min(length, at + 9)
            d.line((x1 + ux * at, y1 + uy * at, x1 + ux * end, y1 + uy * end), fill=color, width=width)
            at += 16


def card(x, y, w, title, rows):
    h = 50 + 31 * len(rows) + 17
    d.rounded_rectangle((x + 5, y + 6, x + w + 5, y + h + 6), radius=10, fill='#E8ECF1')
    d.rounded_rectangle((x, y, x + w, y + h), radius=10, fill='#FFFFFF', outline='#ABBAC9', width=2)
    d.rounded_rectangle((x, y, x + w, y + 48), radius=10, fill='#F4E7C9')
    d.rectangle((x, y + 38, x + w, y + 48), fill='#F4E7C9')
    d.text((x + 19, y + 9), title, font=card_font, fill='#25364D')
    for i, (key, name, typ, changed) in enumerate(rows):
        top = y + 50 + i * 31
        if changed:
            d.rectangle((x + 7, top + 1, x + w - 7, top + 29), fill='#E6F6E9')
        d.text((x + 15, top + 2), key, font=small_font, fill='#B87916' if key == 'PK' else '#3872AD' if key == 'FK' else '#8492A1')
        d.text((x + 60, top + 2), name, font=field_font, fill='#26364C')
        width = d.textbbox((0, 0), typ, font=small_font)[2]
        d.text((x + w - width - 15, top + 4), typ, font=small_font, fill='#748397')
    return h


d.text((80, 35), 'ProPitch ERD v8  |  분석 · 내용 평가 영역', font=title_font, fill='#172A43')
d.text((80, 85), '전체 23개 테이블은 DBML 파일에 포함 · 초록색 행은 v8 추가/수정', font=sub_font, fill='#58718B')

d.rounded_rectangle((50, 145, 1850, 770), radius=18, fill='#F1F6FB', outline='#D8E4EF', width=2)
d.text((80, 165), 'A. 분석 입력과 리포트', font=sub_font, fill='#245D96')

# Solid FK relationships, drawn behind cards.
line([(520, 315), (620, 315)])
label(570, 294, '1 : N')
line([(1060, 315), (1160, 315)])
label(1110, 294, '1 : N')
line([(300, 400), (300, 475)])
label(330, 440, '1 : N')
line([(520, 580), (620, 580)])
label(570, 560, '1 : N')
line([(1060, 580), (1160, 580)])
label(1110, 560, '1 : 0..1')
line([(300, 682), (300, 733), (1380, 733), (1380, 682)])
label(835, 731, 'rounds ↔ reports  1 : 0..1')
line([(840, 400), (840, 475)], dash=True, color='#4FA77C')
label(945, 440, '자료 스냅샷(JSON)')

card(80, 220, 440, 'projects', [
    ('PK', 'id', 'uuid', False),
    ('FK', 'scoring_policy_id', 'uuid', False),
    ('', 'topic', 'varchar', False),
    ('', 'target_minutes', 'int', False),
])
card(620, 220, 440, 'materials', [
    ('PK', 'id', 'uuid', False),
    ('FK', 'project_id', 'uuid', False),
    ('', 'storage_key  UNIQUE', 'varchar', True),
    ('', 'index_status', 'varchar', False),
])
card(1160, 220, 440, 'material_chunks', [
    ('PK', 'id', 'uuid', False),
    ('FK', 'material_id', 'uuid', False),
    ('', 'page_no', 'int', True),
    ('', 'text', 'text', False),
])
card(80, 475, 440, 'rounds', [
    ('PK', 'id', 'uuid', False),
    ('FK', 'project_id', 'uuid', False),
    ('', 'video_key', 'varchar', False),
    ('', 'duration_sec', 'numeric', False),
])
card(620, 475, 440, 'analysis_jobs', [
    ('PK', 'id', 'uuid', False),
    ('FK', 'round_id', 'uuid', False),
    ('', 'attempt', 'int', False),
    ('', 'input_snapshot', 'jsonb', True),
    ('', 'model_ver', 'varchar', False),
])
card(1160, 475, 440, 'reports', [
    ('PK', 'id', 'uuid', False),
    ('FK', 'round_id  UNIQUE', 'uuid', False),
    ('FK', 'job_id  UNIQUE', 'uuid', False),
    ('', 'content_check', 'jsonb', False),
    ('', 'coaching', 'jsonb', True),
])

d.rounded_rectangle((50, 800, 1850, 1360), radius=18, fill='#F7F8FB', outline='#D8E4EF', width=2)
d.text((80, 820), 'B. 루브릭 점수와 근거', font=sub_font, fill='#245D96')

line([(520, 970), (620, 970)])
label(570, 948, '1 : N')
line([(1060, 970), (1160, 970)])
label(1110, 948, '1 : N')
line([(300, 1055), (300, 1115)])
label(330, 1085, '정책 2개 참조')
line([(1380, 1060), (1380, 1115)])
label(1420, 1085, '1 : N')

card(80, 875, 440, 'rubrics', [
    ('PK', 'id', 'uuid', False),
    ('', 'kind  COMMON / EXPERT', 'varchar', False),
    ('', 'version', 'varchar', False),
])
card(620, 875, 440, 'rubric_items', [
    ('PK', 'id', 'uuid', False),
    ('FK', 'rubric_id', 'uuid', False),
    ('', 'scoring_guide', 'text', False),
    ('', 'evaluation_domain', 'varchar', True),
    ('', 'weight', 'numeric', False),
])
card(1160, 875, 440, 'report_scores', [
    ('PK', 'id', 'uuid', False),
    ('FK', 'report_id', 'uuid', False),
    ('FK', 'rubric_item_id', 'uuid', False),
    ('', 'score', 'int', False),
    ('', 'evidence', 'jsonb', True),
])
card(80, 1115, 440, 'scoring_policies', [
    ('PK', 'id', 'uuid', False),
    ('FK', 'common_rubric_id', 'uuid', False),
    ('FK', 'expert_rubric_id', 'uuid', False),
    ('', 'common/expert_weight', 'numeric', False),
])
card(1160, 1115, 440, 'reports (반복 표시)', [
    ('PK', 'id', 'uuid', False),
    ('', 'common_score', 'int', False),
    ('', 'expert_score', 'int', False),
    ('', 'total_score', 'int', False),
])
d.text((640, 1250), '점수 근거: 영상 시각 + 전사 발췌 + 선택적 PDF 페이지/청크', font=small_font, fill='#496079')
d.text((640, 1280), '점선은 FK가 아닌 분석 입력 스냅샷 관계', font=small_font, fill='#4B9B76')

im.save(OUT)
print(OUT)
