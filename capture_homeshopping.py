# -*- coding: utf-8 -*-
"""
홈쇼핑 일일 자동 캡처 & HTML 업데이트 스크립트
실행 시각: 매일 오전 10시 (Windows 작업 스케줄러)
"""

from playwright.sync_api import sync_playwright
from datetime import date
import os, glob, shutil, base64, json

BASE_DIR    = r'C:\AI\claude_with_lakehouse'
ARCHIVE_DIR = os.path.join(BASE_DIR, 'captures')
TODAY       = date.today().strftime('%Y.%m.%d')
TODAY_KEY   = date.today().strftime('%Y-%m-%d')

MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
VIEWPORT  = {'width': 390, 'height': 844}


def close_popups(page):
    for text in ['닫기', '오늘 그만 보기']:
        try:
            page.get_by_text(text, exact=True).first.click(timeout=2000)
            page.wait_for_timeout(400)
        except: pass
    for sel in ['.btn_cls_this', '.pop_close', '.btn_close', '.layer_item.ly_main_pop.open .btn_close']:
        try:
            for btn in page.locator(sel).all():
                if btn.is_visible():
                    btn.click(timeout=1000)
                    page.wait_for_timeout(300)
        except: pass


def close_popups_gs(page):
    """GS SHOP 전용 팝업 닫기"""
    close_popups(page)
    try:
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
    except: pass
    for sel in ['.pop-close', '.btn-close', '.close-btn', '.ly-close',
                '[class*=close]', '[class*=popup] [class*=close]',
                'button:has-text("닫기")', 'button:has-text("오늘 하루 안보기")']:
        try:
            for btn in page.locator(sel).all():
                if btn.is_visible():
                    btn.click(timeout=1000)
                    page.wait_for_timeout(300)
        except: pass
    try:
        page.locator('.dimmed, .dim, .overlay, .bg-dim').first.click(timeout=1000)
        page.wait_for_timeout(300)
    except: pass


def click_next_tab(page, home_label='홈'):
    """홈 탭 오른쪽 탭 클릭 (home_label: 홈 탭 텍스트)"""
    return page.evaluate("""
        (homeLabel) => {
            const tabs = Array.from(document.querySelectorAll('.tab_menu a, .gnb_menu a, [class*=tab] a'));
            const homeIdx = tabs.findIndex(a => a.innerText.trim() === homeLabel);
            if (homeIdx >= 0 && homeIdx+1 < tabs.length) {
                const next = tabs[homeIdx+1];
                next.click();
                return next.innerText.trim();
            }
            return null;
        }
    """, home_label)


def capture_full(page, path):
    page.screenshot(path=path, full_page=True)
    return path


def capture_banner(page, path, height=600):
    """상단 배너 영역만 크롭 저장 (메인 프로모션명 판독용)"""
    page.screenshot(path=path, clip={'x': 0, 'y': 0, 'width': VIEWPORT['width'], 'height': height})
    return path


def save_page_text(page, path):
    """페이지 본문 텍스트 추출 저장 (요약 시 참고용)"""
    try:
        text = page.inner_text('body')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
    except: pass


def run_hyundai(browser, archive_dir):
    """현대홈쇼핑 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://www.hmall.com', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)
    close_popups(page)
    page.wait_for_timeout(500)
    # hmall 전용 팝업 닫기
    for sel in ['.sc-co-popup .btn-close', '.layer-popup .btn-close', '.pop_wrap .btn_close',
                '[class*=popup] [class*=close]', '.recentdim']:
        try:
            for btn in page.locator(sel).all():
                if btn.is_visible():
                    btn.click(timeout=1000)
                    page.wait_for_timeout(300)
        except: pass
    close_popups(page)
    tab_name = page.evaluate("""
        () => {
            const tabs = Array.from(document.querySelectorAll('[class*=main] nav a, .sc-dp-display nav a'));
            const idx = tabs.findIndex(a => a.innerText.trim() === '현대홈쇼핑');
            if (idx >= 0 && idx+1 < tabs.length) {
                const next = tabs[idx+1];
                next.click();
                return next.innerText.trim();
            }
            return null;
        }
    """)
    page.wait_for_timeout(2000)
    close_popups(page)
    capture_full(page, os.path.join(archive_dir, 'hyundai_next_tab_full.png'))
    capture_banner(page, os.path.join(archive_dir, 'hyundai_banner.png'))
    save_page_text(page, os.path.join(archive_dir, 'hyundai_page_text.txt'))
    page.close()
    return tab_name


def run_gs(browser, archive_dir):
    """GS SHOP 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://m.gsshop.com', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(3000)
    close_popups_gs(page)
    page.wait_for_timeout(1000)
    close_popups_gs(page)
    tab_name = click_next_tab(page)
    page.wait_for_timeout(2000)
    close_popups_gs(page)
    capture_full(page, os.path.join(archive_dir, 'gs_next_tab_full.png'))
    capture_banner(page, os.path.join(archive_dir, 'gs_banner.png'))
    save_page_text(page, os.path.join(archive_dir, 'gs_page_text.txt'))
    page.close()
    return tab_name


def run_cj(browser, archive_dir):
    """CJ온스타일 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(3000)
    close_popups(page)
    tab_name = click_next_tab(page)
    page.wait_for_timeout(2000)
    close_popups(page)
    capture_full(page, os.path.join(archive_dir, 'cj_next_tab_full.png'))
    capture_banner(page, os.path.join(archive_dir, 'cj_banner.png'))
    save_page_text(page, os.path.join(archive_dir, 'cj_page_text.txt'))
    page.close()
    return tab_name


def run_lotte(browser, archive_dir):
    """롯데홈쇼핑 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://m.lotteimall.com', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(3000)
    close_popups(page)
    tab_name = click_next_tab(page)
    page.wait_for_timeout(2000)
    capture_full(page, os.path.join(archive_dir, 'lotte_next_tab_full.png'))
    capture_banner(page, os.path.join(archive_dir, 'lotte_banner.png'))
    save_page_text(page, os.path.join(archive_dir, 'lotte_page_text.txt'))
    page.close()
    return tab_name


def get_archive_dates():
    """captures/ 아래 날짜 폴더 목록 (내림차순)"""
    folders = sorted(
        [os.path.basename(d) for d in glob.glob(os.path.join(ARCHIVE_DIR, '????-??-??'))
         if os.path.isdir(d)],
        reverse=True
    )
    return folders


def _img_content(path):
    with open(path, 'rb') as f:
        data = base64.standard_b64encode(f.read()).decode('ascii')
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': data}}


def _ask_claude(img_path, prompt, text_path=None, banner_path=None):
    """claude CLI subprocess로 배너+전체이미지+페이지텍스트 분석"""
    import subprocess

    content = []
    # 배너(상단 크롭)를 먼저 — 메인 프로모션명 판독 우선
    if banner_path and os.path.exists(banner_path):
        content.append({'type': 'text', 'text': '[메인 배너 (상단 크롭, 고해상도)]'})
        content.append(_img_content(banner_path))
    content.append({'type': 'text', 'text': '[전체 페이지 캡처]'})
    content.append(_img_content(img_path))
    if text_path and os.path.exists(text_path):
        with open(text_path, encoding='utf-8', errors='replace') as f:
            page_text = f.read()[:8000]
        content.append({'type': 'text', 'text': f'[페이지 텍스트 원문]\n{page_text}'})
    content.append({'type': 'text', 'text': prompt})

    payload = {
        'type': 'user',
        'message': {'role': 'user', 'content': content},
    }
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    proc = subprocess.run(
        ['claude', '-p', '--verbose', '--input-format', 'stream-json', '--output-format', 'stream-json'],
        input=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        capture_output=True, env=env, timeout=120,
    )
    for line in proc.stdout.decode('utf-8', errors='replace').splitlines():
        try:
            obj = json.loads(line)
            if obj.get('type') == 'result':
                return obj.get('result', '').strip()
        except:
            pass
    return ''


PROMO_HISTORY_PATH = os.path.join(BASE_DIR, 'promo_history.json')


def load_promo_history():
    if os.path.exists(PROMO_HISTORY_PATH):
        with open(PROMO_HISTORY_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_promo_history(history):
    with open(PROMO_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def update_promo_start(summaries):
    """프로모션명 변경 감지 → 시작일 갱신, 동일 프로모션이면 최초 시작일 유지"""
    history = load_promo_history()
    for brand, s in summaries.items():
        if not isinstance(s, dict):
            continue
        name = s.get('name', '').strip()
        if not name:
            continue
        prev = history.get(brand, {})
        if prev.get('name') == name:
            # 같은 프로모션 → 최초 시작일 유지, period 앞부분 교체
            s['start'] = prev['start']
        else:
            # 새 프로모션 → 오늘을 시작일로 기록
            s['start'] = TODAY_KEY
            history[brand] = {'name': name, 'start': TODAY_KEY}
    save_promo_history(history)
    return summaries


def parse_summary_text(text):
    """요약 텍스트에서 기간/프로모션명/혜택 본문 분리"""
    period, name, body_lines = '', '', []
    for line in text.strip().splitlines():
        if line.startswith('기간:'):
            period = line[3:].strip()
        elif line.startswith('프로모션명:'):
            name = line[6:].strip()
        else:
            body_lines.append(line)
    return {'period': period, 'name': name, 'body': '\n'.join(body_lines).strip()}


# 브랜드명 단독 탭 — 프로모션이 아닌 업체/브랜드 전용관 탭명 목록
# 새로 발견되면 여기에 추가
HYUNDAI_BRAND_TABS = {
    '한국금거래소',
}

def is_brand_tab(tab_name):
    """탭명이 브랜드/업체 전용관이면 True (프로모션 행사가 아님)"""
    if not tab_name:
        return False
    return tab_name.strip() in HYUNDAI_BRAND_TABS


HYUNDAI_PROMPT_EXTRA = (
    '현대홈쇼핑은 매일 행사가 있지 않습니다. '
    '진행 중인 행사가 없으면 프로모션명에 "해당없음"이라고 쓰고 혜택 행은 모두 생략하세요. '
    '탭명이 특정 브랜드나 업체명(예: 한국금거래소, 특정 쇼핑몰 이름 등)인 경우에도 '
    '프로모션 행사가 아닌 브랜드관으로 판단하여 "해당없음"으로 처리하세요.'
)


def generate_summary(archive_date_dir, hyundai_tab, gs_tab, cj_tab, lotte_tab):
    """캡처 이미지를 claude CLI로 분석해 행사 요약 생성"""
    summaries = {}

    # 현대홈쇼핑: 브랜드 탭이면 AI 분석 없이 즉시 해당없음 처리
    if is_brand_tab(hyundai_tab):
        print(f'현대 브랜드탭 감지 ({hyundai_tab}) → 해당없음 처리')
        summaries['hyundai'] = {'period': '', 'name': '해당없음', 'body': ''}

    for brand, filename, label, extra in [
        ('hyundai', 'hyundai_next_tab_full.png', hyundai_tab or '현대홈쇼핑', HYUNDAI_PROMPT_EXTRA),
        ('gs',      'gs_next_tab_full.png',      gs_tab      or 'GS SHOP',    ''),
        ('cj',      'cj_next_tab_full.png',       cj_tab      or 'CJ온스타일', ''),
        ('lotte',   'lotte_next_tab_full.png',    lotte_tab   or '롯데홈쇼핑', ''),
    ]:
        if brand in summaries:  # 이미 처리된 경우(브랜드탭 등) 건너뜀
            continue
        img_path = os.path.join(archive_date_dir, filename)
        if not os.path.exists(img_path):
            summaries[brand] = {'period': '', 'name': '', 'body': '이미지 없음'}
            continue
        prompt = (
            f'{label} 홈쇼핑 모바일 캡처본입니다. '
            '텍스트 원문을 우선 참고하고, 이미지는 시각적 구성 파악에 활용해주세요.\n\n'
            + (extra + '\n\n' if extra else '') +
            '규칙:\n'
            '- **, ##, --- 등 마크다운 기호 절대 사용 금지\n'
            '- 부연 설명, 안내 문구 추가 금지\n'
            '- 확인되지 않는 항목은 행 자체를 생략\n\n'
            '형식:\n'
            '기간: (행사 기간)\n'
            '프로모션명: (메인 행사명 하나만, 서브 행사명 나열 금지)\n'
            '혜택:\n'
            '  혜택종류: 혜택상세\n\n'
            '기간 작성 규칙:\n'
            '- 반드시 "M/DD ~ M/DD" 형식으로 작성 (예: 5/13 ~ 5/17)\n'
            '- 종료일만 알면 "~ M/DD" 형식으로 작성\n'
            '- 날짜를 전혀 확인할 수 없으면 기간 행 자체를 생략\n'
            '- "상반기", "기간 미확인" 등 모호한 표현 절대 금지\n\n'
            '혜택종류는 카드, 적립, 사은품, 경품, 할인, 특가, 쿠폰 중에서 선택하세요.\n'
            '혜택상세에는 혜택 내용과 함께 적용 조건(카드사명, 선착순 인원, 최대 금액, 기간 등)도 함께 적어주세요.\n'
            '혜택이 여러 개면 줄을 나눠 작성하세요.'
        )
        text_path   = img_path.replace('_next_tab_full.png', '_page_text.txt')
        banner_path = img_path.replace('_next_tab_full.png', '_banner.png')
        try:
            raw = _ask_claude(img_path, prompt, text_path, banner_path)
            summaries[brand] = parse_summary_text(raw)
            print(f'{brand} 요약 완료')
        except Exception as e:
            print(f'{brand} 요약 실패: {e}')
            summaries[brand] = {'period': '', 'name': '', 'body': '요약 생성 실패'}

    update_promo_start(summaries)

    summary_path = os.path.join(archive_date_dir, 'summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    return summaries


def _extract_end_date(period):
    """기간 문자열에서 끝날짜만 추출 (숫자가 포함된 경우만 유효로 판단)"""
    import re
    # ~ 또는 - 로 구분된 마지막 부분 추출
    if '~' in period:
        end = period.split('~')[-1].strip()
    elif ' - ' in period or '–' in period:
        end = re.split(r' - |–', period)[-1].strip()
    else:
        return None
    # 날짜처럼 보이는 경우만 유효 (M/DD, M.DD, YYYY-MM-DD 등)
    if re.search(r'\d{1,4}[./-]\d{1,2}', end):
        return end
    return None


def _fmt_start(start_iso):
    """YYYY-MM-DD → M/DD 형식으로 변환"""
    parts = start_iso.split('-')
    if len(parts) == 3:
        return f'{int(parts[1])}/{parts[2]}'
    return start_iso


def _s(brand_data, key, fallback=''):
    """summary dict 또는 구버전 string 에서 값 추출"""
    if not isinstance(brand_data, dict):
        return fallback if key != 'body' else str(brand_data)
    if key == 'period':
        start = brand_data.get('start', '')
        period = brand_data.get('period', '')
        end = _extract_end_date(period) if period else None
        if start and end:
            return f'{_fmt_start(start)} ~ {end}'
        elif start:
            return _fmt_start(start)
        return period or fallback
    return brand_data.get(key, fallback)


def update_html(hyundai_tab, gs_tab, cj_tab, lotte_tab, archive_dates):
    all_summaries = {}
    for d in archive_dates:
        sp = os.path.join(ARCHIVE_DIR, d, 'summary.json')
        if os.path.exists(sp):
            with open(sp, encoding='utf-8') as f:
                all_summaries[d] = json.load(f)

    summaries_js = json.dumps(all_summaries, ensure_ascii=False)
    latest = archive_dates[0] if archive_dates else TODAY_KEY
    latest_s = all_summaries.get(latest, {})

    no_body = '캡처 완료 — 행사 내용은 위 이미지를 확인하세요'
    hyundai_name = _s(latest_s.get('hyundai', {}), 'name',   hyundai_tab or '현대홈쇼핑')
    gs_name      = _s(latest_s.get('gs',      {}), 'name',   gs_tab      or 'GS SHOP')
    cj_name      = _s(latest_s.get('cj',      {}), 'name',   cj_tab      or 'CJ온스타일')
    lotte_name   = _s(latest_s.get('lotte',   {}), 'name',   lotte_tab   or '롯데홈쇼핑')
    hyundai_period = _s(latest_s.get('hyundai', {}), 'period', TODAY)
    gs_period      = _s(latest_s.get('gs',      {}), 'period', TODAY)
    cj_period      = _s(latest_s.get('cj',      {}), 'period', TODAY)
    lotte_period   = _s(latest_s.get('lotte',   {}), 'period', TODAY)
    hyundai_body = _s(latest_s.get('hyundai', {}), 'body',   no_body)
    gs_body      = _s(latest_s.get('gs',      {}), 'body',   no_body)
    cj_body      = _s(latest_s.get('cj',      {}), 'body',   no_body)
    lotte_body   = _s(latest_s.get('lotte',   {}), 'body',   no_body)

    hyundai_no_event = (hyundai_name == '해당없음')

    date_nav_items = '\n'.join(
        f'<button class="date-btn{" active" if d == latest else ""}" onclick="switchDate(\'{d}\')">{d}</button>'
        for d in archive_dates
    )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>홈쇼핑 행사 요약 — {TODAY}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; background: #f4f6f9; color: #222; }}
    header {{ background: #1a1a2e; color: white; padding: 20px 32px; display: flex; align-items: center; gap: 12px; }}
    header h1 {{ font-size: 20px; font-weight: 700; }}
    header span {{ font-size: 14px; color: #aaa; margin-left: auto; }}
    .date-nav {{ max-width: 1600px; margin: 20px auto 0; padding: 0 24px; display: flex; gap: 8px; flex-wrap: wrap; }}
    .date-btn {{ padding: 6px 14px; border-radius: 20px; border: 1px solid #ddd; background: white; font-size: 13px; cursor: pointer; color: #555; }}
    .date-btn.active {{ background: #1a1a2e; color: white; border-color: #1a1a2e; font-weight: 700; }}
    .container {{ max-width: 1800px; margin: 20px auto 32px; padding: 0 24px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }}
    .card {{ background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; }}
    .card.no-event {{ opacity: 0.55; }}
    .card-header {{ padding: 14px 20px; border-bottom: 1px solid #f0f0f0; }}
    .card-header-top {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
    .logo {{ font-size: 12px; font-weight: 800; padding: 5px 10px; border-radius: 8px; color: white; white-space: nowrap; }}
    .logo.hyundai {{ background: #e65100; }} .logo.gs {{ background: #1565c0; }} .logo.cj {{ background: #7b1fa2; }} .logo.lotte {{ background: #c62828; }}
    .promo-name {{ font-size: 16px; font-weight: 700; flex: 1; }}
    .promo-period {{ font-size: 12px; color: #fff; background: #ff6b35; padding: 3px 10px; border-radius: 20px; white-space: nowrap; }}
    .card-body {{ display: flex; }}
    .screenshot-wrap {{ width: 160px; min-width: 160px; border-right: 1px solid #f0f0f0; padding: 12px; display: flex; flex-direction: column; align-items: center; gap: 8px; background: #fafafa; }}
    .screenshot-wrap p {{ font-size: 11px; color: #999; }}
    .screenshot-wrap img {{ width: 100%; border-radius: 8px; border: 1px solid #eee; cursor: pointer; transition: transform 0.2s; }}
    .screenshot-wrap img:hover {{ transform: scale(1.02); }}
    .summary {{ flex: 1; padding: 16px 20px; overflow-y: auto; max-height: 600px; font-size: 13px; line-height: 1.8; color: #444; white-space: pre-wrap; }}
    .modal {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 1000; justify-content: center; align-items: flex-start; padding: 24px; overflow-y: auto; }}
    .modal.open {{ display: flex; }}
    .modal img {{ max-width: 390px; width: 100%; border-radius: 12px; margin: auto; }}
    .modal-close {{ position: fixed; top: 16px; right: 20px; color: white; font-size: 32px; cursor: pointer; z-index: 1001; }}
  </style>
</head>
<body>
<header>
  <h1>홈쇼핑 행사 요약</h1>
  <span id="header-date">기준일: {TODAY} 오전 10시 자동 캡처</span>
</header>
<div class="date-nav" id="date-nav">
{date_nav_items}
</div>
<div class="container">
  <div class="card">
    <div class="card-header">
      <div class="card-header-top">
        <span class="logo gs">GS SHOP</span>
        <span class="promo-name" id="gs-name">{gs_name}</span>
      </div>
      <span class="promo-period" id="gs-period">{gs_period}</span>
    </div>
    <div class="card-body">
      <div class="screenshot-wrap">
        <p>모바일 캡처본</p>
        <img id="gs-img" src="captures/{latest}/gs_next_tab_full.png" alt="GS SHOP" onclick="openModal(this.src)">
        <p style="font-size:10px;color:#bbb;">클릭하면 크게 보기</p>
      </div>
      <div class="summary" id="gs-summary">{gs_body}</div>
    </div>
  </div>
  <div class="card">
    <div class="card-header">
      <div class="card-header-top">
        <span class="logo cj">CJ온스타일</span>
        <span class="promo-name" id="cj-name">{cj_name}</span>
      </div>
      <span class="promo-period" id="cj-period">{cj_period}</span>
    </div>
    <div class="card-body">
      <div class="screenshot-wrap">
        <p>모바일 캡처본</p>
        <img id="cj-img" src="captures/{latest}/cj_next_tab_full.png" alt="CJ온스타일" onclick="openModal(this.src)">
        <p style="font-size:10px;color:#bbb;">클릭하면 크게 보기</p>
      </div>
      <div class="summary" id="cj-summary">{cj_body}</div>
    </div>
  </div>
  <div class="card">
    <div class="card-header">
      <div class="card-header-top">
        <span class="logo lotte">롯데홈쇼핑</span>
        <span class="promo-name" id="lotte-name">{lotte_name}</span>
      </div>
      <span class="promo-period" id="lotte-period">{lotte_period}</span>
    </div>
    <div class="card-body">
      <div class="screenshot-wrap">
        <p>모바일 캡처본</p>
        <img id="lotte-img" src="captures/{latest}/lotte_next_tab_full.png" alt="롯데홈쇼핑" onclick="openModal(this.src)">
        <p style="font-size:10px;color:#bbb;">클릭하면 크게 보기</p>
      </div>
      <div class="summary" id="lotte-summary">{lotte_body}</div>
    </div>
  </div>
  <div class="card{'  no-event' if hyundai_no_event else ''}">
    <div class="card-header">
      <div class="card-header-top">
        <span class="logo hyundai">현대홈쇼핑</span>
        <span class="promo-name" id="hyundai-name">{'행사 없음' if hyundai_no_event else hyundai_name}</span>
      </div>
      {'<span class="promo-period" style="background:#bbb;">행사 없음</span>' if hyundai_no_event else f'<span class="promo-period" id="hyundai-period">{hyundai_period}</span>'}
    </div>
    <div class="card-body">
      <div class="screenshot-wrap">
        <p>모바일 캡처본</p>
        <img id="hyundai-img" src="captures/{latest}/hyundai_next_tab_full.png" alt="현대홈쇼핑" onclick="openModal(this.src)">
        <p style="font-size:10px;color:#bbb;">클릭하면 크게 보기</p>
      </div>
      <div class="summary" id="hyundai-summary">{hyundai_body}</div>
    </div>
  </div>
</div>
<div class="modal" id="modal" onclick="closeModal()">
  <span class="modal-close" onclick="closeModal()">✕</span>
  <img id="modal-img" src="" alt="">
</div>
<script>
  const summaries = {summaries_js};
  const NO_BODY = '캡처 완료 — 행사 내용은 위 이미지를 확인하세요';
  function g(id) {{ return document.getElementById(id); }}
  function s(d) {{ return summaries[d] || {{}}; }}
  function sv(obj, key, fb) {{ return (obj[key] && typeof obj[key]==='object' ? obj[key].name||obj[key].period||obj[key].body : null) || (typeof obj[key]==='string' ? obj[key] : null) || fb; }}
  function fmtStart(iso) {{
    const p = iso.split('-'); return p.length===3 ? parseInt(p[1])+'/'+p[2] : iso;
  }}
  function extractEnd(period) {{
    let end = '';
    if (period.includes('~')) end = period.split('~').pop().trim();
    else if (period.includes(' - ')) end = period.split(' - ').pop().trim();
    else if (period.includes('–')) end = period.split('–').pop().trim();
    return /[0-9]{1,4}[./-][0-9]{1,2}/.test(end) ? end : null;
  }}
  function sfield(obj, brand, field, fb) {{
    const b = obj[brand]; if (!b) return fb;
    if (typeof b !== 'object') return field==='body' ? b : fb;
    if (field === 'period') {{
      const start = b.start || '';
      const period = b.period || '';
      const end = period ? extractEnd(period) : null;
      if (start && end) return fmtStart(start) + ' ~ ' + end;
      if (start) return fmtStart(start);
      return period || fb;
    }}
    return b[field] || fb;
  }}
  function openModal(src) {{ g('modal-img').src = src; g('modal').classList.add('open'); }}
  function closeModal() {{ g('modal').classList.remove('open'); }}
  function switchDate(d) {{
    const obj = s(d);
    g('hyundai-img').src = 'captures/' + d + '/hyundai_next_tab_full.png';
    g('gs-img').src      = 'captures/' + d + '/gs_next_tab_full.png';
    g('cj-img').src      = 'captures/' + d + '/cj_next_tab_full.png';
    g('lotte-img').src   = 'captures/' + d + '/lotte_next_tab_full.png';
    g('hyundai-name').textContent = sfield(obj,'hyundai','name','현대홈쇼핑');
    g('gs-name').textContent      = sfield(obj,'gs','name','GS SHOP');
    g('cj-name').textContent      = sfield(obj,'cj','name','CJ온스타일');
    g('lotte-name').textContent   = sfield(obj,'lotte','name','롯데홈쇼핑');
    const hp = g('hyundai-period'); if (hp) hp.textContent = sfield(obj,'hyundai','period',d);
    g('gs-period').textContent    = sfield(obj,'gs','period',d);
    g('cj-period').textContent    = sfield(obj,'cj','period',d);
    g('lotte-period').textContent = sfield(obj,'lotte','period',d);
    g('hyundai-summary').textContent = sfield(obj,'hyundai','body',NO_BODY);
    g('gs-summary').textContent      = sfield(obj,'gs','body',NO_BODY);
    g('cj-summary').textContent      = sfield(obj,'cj','body',NO_BODY);
    g('lotte-summary').textContent   = sfield(obj,'lotte','body',NO_BODY);
    g('header-date').textContent = '기준일: ' + d;
    document.querySelectorAll('.date-btn').forEach(b => b.classList.toggle('active', b.textContent === d));
  }}
</script>
</body>
</html>"""

    with open(os.path.join(BASE_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'HTML 업데이트 완료: {TODAY}')


def git_push(archive_date_dir):
    """캡처 결과를 GitHub에 자동 push"""
    import subprocess
    rel = os.path.relpath(archive_date_dir, BASE_DIR).replace('\\', '/')
    candidates = [
        'index.html', 'promo_history.json',
        f'{rel}/hyundai_next_tab_full.png', f'{rel}/hyundai_banner.png', f'{rel}/hyundai_page_text.txt',
        f'{rel}/gs_next_tab_full.png',      f'{rel}/gs_banner.png',      f'{rel}/gs_page_text.txt',
        f'{rel}/cj_next_tab_full.png',      f'{rel}/cj_banner.png',      f'{rel}/cj_page_text.txt',
        f'{rel}/lotte_next_tab_full.png',   f'{rel}/lotte_banner.png',   f'{rel}/lotte_page_text.txt',
        f'{rel}/summary.json',
    ]
    files_to_add = [f for f in candidates if os.path.exists(os.path.join(BASE_DIR, f.replace('/', os.sep)))]
    cmds = [
        ['git', '-C', BASE_DIR, 'add', '--force'] + files_to_add,
        ['git', '-C', BASE_DIR, 'commit', '-m', f'Auto update: {TODAY}'],
        ['git', '-C', BASE_DIR, 'push', 'origin', 'main'],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout or result.stderr)


if __name__ == '__main__':
    import sys
    # 로그 파일로도 출력 (작업 스케줄러 실행 시 stdout 확인용)
    log_path = os.path.join(BASE_DIR, 'capture_log.txt')
    log_f = open(log_path, 'a', encoding='utf-8')
    class Tee:
        def write(self, msg):
            sys.__stdout__.write(msg)
            log_f.write(msg)
        def flush(self):
            sys.__stdout__.flush()
            log_f.flush()
    sys.stdout = Tee()

    print(f'\n[{TODAY}] 홈쇼핑 자동 캡처 시작...')

    archive_date_dir = os.path.join(ARCHIVE_DIR, TODAY_KEY)
    os.makedirs(archive_date_dir, exist_ok=True)

    hyundai_tab = gs_tab = cj_tab = lotte_tab = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, func in [('현대', run_hyundai), ('GS', run_gs), ('CJ', run_cj), ('롯데', run_lotte)]:
            try:
                tab = func(browser, archive_date_dir)
                print(f'{name} 완료: {tab}')
                if name == '현대': hyundai_tab = tab
                elif name == 'GS': gs_tab = tab
                elif name == 'CJ': cj_tab = tab
                elif name == '롯데': lotte_tab = tab
            except Exception as e:
                print(f'{name} 캡처 실패: {e}')
        browser.close()

    print('AI 요약 생성 중...')
    try:
        generate_summary(archive_date_dir, hyundai_tab, gs_tab, cj_tab, lotte_tab)
    except Exception as e:
        print(f'요약 실패: {e}')

    archive_dates = get_archive_dates()
    update_html(hyundai_tab, gs_tab, cj_tab, lotte_tab, archive_dates)
    git_push(archive_date_dir)
    print('전체 완료! GitHub Pages 자동 업데이트됨')
    log_f.close()
