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


def click_next_tab(page):
    """홈 탭 오른쪽 탭 클릭"""
    return page.evaluate("""
        () => {
            const tabs = Array.from(document.querySelectorAll('.tab_menu a, .gnb_menu a, [class*=tab] a'));
            const homeIdx = tabs.findIndex(a => a.innerText.trim() === '홈');
            if (homeIdx >= 0 && homeIdx+1 < tabs.length) {
                const next = tabs[homeIdx+1];
                next.click();
                return next.innerText.trim();
            }
            return null;
        }
    """)


def capture_full(page, path):
    page.screenshot(path=path, full_page=True)
    return path


def close_popups_gs(page):
    """GS SHOP 전용 팝업 닫기"""
    # 공통 닫기 먼저
    close_popups(page)
    # GS 특유의 웰컴/이벤트 팝업: ESC 또는 레이어 외부 클릭
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
    # 팝업 레이어 뒤 배경 클릭으로 닫기 시도
    try:
        page.locator('.dimmed, .dim, .overlay, .bg-dim').first.click(timeout=1000)
        page.wait_for_timeout(300)
    except: pass


def save_page_text(page, path):
    """페이지 본문 텍스트 추출 저장 (요약 시 참고용)"""
    try:
        text = page.inner_text('body')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
    except: pass


def run_gs(browser, archive_dir):
    """GS SHOP 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://m.gsshop.com', wait_until='load', timeout=30000)
    page.wait_for_timeout(3000)
    close_popups_gs(page)
    page.wait_for_timeout(1000)
    close_popups_gs(page)
    tab_name = click_next_tab(page)
    page.wait_for_timeout(2000)
    close_popups_gs(page)
    capture_full(page, os.path.join(archive_dir, 'gs_next_tab_full.png'))
    save_page_text(page, os.path.join(archive_dir, 'gs_page_text.txt'))
    page.close()
    return tab_name


def run_cj(browser, archive_dir):
    """CJ온스타일 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005', wait_until='load', timeout=30000)
    page.wait_for_timeout(3000)
    close_popups(page)
    tab_name = click_next_tab(page)
    page.wait_for_timeout(2000)
    close_popups(page)
    capture_full(page, os.path.join(archive_dir, 'cj_next_tab_full.png'))
    save_page_text(page, os.path.join(archive_dir, 'cj_page_text.txt'))
    page.close()
    return tab_name


def run_lotte(browser, archive_dir):
    """롯데홈쇼핑 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://m.lotteimall.com', wait_until='load', timeout=30000)
    page.wait_for_timeout(3000)
    close_popups(page)
    tab_name = click_next_tab(page)
    page.wait_for_timeout(2000)
    capture_full(page, os.path.join(archive_dir, 'lotte_next_tab_full.png'))
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


def _ask_claude(img_path, prompt, text_path=None):
    """claude CLI subprocess로 이미지+페이지텍스트 분석"""
    import subprocess
    with open(img_path, 'rb') as f:
        img_data = base64.standard_b64encode(f.read()).decode('ascii')

    content = [
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': img_data}},
    ]
    if text_path and os.path.exists(text_path):
        with open(text_path, encoding='utf-8', errors='replace') as f:
            page_text = f.read()[:8000]  # 토큰 절약
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


def generate_summary(archive_date_dir, gs_tab, cj_tab, lotte_tab):
    """캡처 이미지를 claude CLI로 분석해 행사 요약 생성"""
    summaries = {}
    for brand, filename, label in [
        ('gs',    'gs_next_tab_full.png',    gs_tab    or 'GS SHOP'),
        ('cj',    'cj_next_tab_full.png',    cj_tab    or 'CJ온스타일'),
        ('lotte', 'lotte_next_tab_full.png', lotte_tab or '롯데홈쇼핑'),
    ]:
        img_path = os.path.join(archive_date_dir, filename)
        if not os.path.exists(img_path):
            summaries[brand] = '이미지 없음'
            continue
        prompt = (
            f'{label} 홈쇼핑 모바일 캡처본입니다. '
            '이미지에서 확인되는 행사 정보를 아래 형식으로 정리해주세요.\n\n'
            '규칙:\n'
            '- **, ##, --- 등 마크다운 기호 절대 사용 금지\n'
            '- 이미지 해상도, 판독 어려움 등 부연 설명 추가 금지\n'
            '- 확인되지 않는 항목은 행 자체를 생략\n\n'
            '형식:\n'
            '기간: (행사 기간)\n'
            '프로모션명: (행사/기획전 이름)\n'
            '혜택:\n'
            '  혜택종류: 혜택상세\n'
            '  혜택종류: 혜택상세\n\n'
            '혜택종류는 카드, 적립, 사은품, 경품, 할인, 특가, 쿠폰 중에서 선택하세요. 혜택이 여러 개면 줄을 나눠 작성하세요.'
        )
        text_path = img_path.replace('_next_tab_full.png', '_page_text.txt')
        try:
            summaries[brand] = _ask_claude(img_path, prompt, text_path)
            print(f'{brand} 요약 완료')
        except Exception as e:
            print(f'{brand} 요약 실패: {e}')
            summaries[brand] = '요약 생성 실패'

    summary_path = os.path.join(archive_date_dir, 'summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    return summaries


def update_html(gs_tab, cj_tab, lotte_tab, archive_dates):
    # Load summaries for all archived dates
    all_summaries = {}
    for d in archive_dates:
        sp = os.path.join(ARCHIVE_DIR, d, 'summary.json')
        if os.path.exists(sp):
            with open(sp, encoding='utf-8') as f:
                all_summaries[d] = json.load(f)

    summaries_js = json.dumps(all_summaries, ensure_ascii=False)
    latest = archive_dates[0] if archive_dates else TODAY_KEY
    latest_s = all_summaries.get(latest, {})
    no_summary = '캡처 완료 — 행사 내용은 위 이미지를 확인하세요'
    gs_summary_txt    = latest_s.get('gs',    no_summary)
    cj_summary_txt    = latest_s.get('cj',    no_summary)
    lotte_summary_txt = latest_s.get('lotte', no_summary)

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
    .container {{ max-width: 1600px; margin: 20px auto 32px; padding: 0 24px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }}
    .card {{ background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; }}
    .card-header {{ padding: 16px 20px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #f0f0f0; }}
    .logo {{ font-size: 12px; font-weight: 800; padding: 5px 10px; border-radius: 8px; color: white; white-space: nowrap; }}
    .logo.gs {{ background: #00863c; }} .logo.cj {{ background: #e8003d; }} .logo.lotte {{ background: #e60012; }}
    .card-header .title {{ font-size: 16px; font-weight: 700; }}
    .card-header .period {{ margin-left: auto; font-size: 12px; color: #888; background: #f5f5f5; padding: 4px 10px; border-radius: 20px; white-space: nowrap; }}
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
      <span class="logo gs">GS SHOP</span>
      <span class="title" id="gs-title">{gs_tab or '홈 다음 탭'}</span>
      <span class="period" id="gs-period">{TODAY}</span>
    </div>
    <div class="card-body">
      <div class="screenshot-wrap">
        <p>모바일 캡처본</p>
        <img id="gs-img" src="captures/{latest}/gs_next_tab_full.png" alt="GS SHOP" onclick="openModal(this.src)">
        <p style="font-size:10px;color:#bbb;">클릭하면 크게 보기</p>
      </div>
      <div class="summary" id="gs-summary">{gs_summary_txt}</div>
    </div>
  </div>
  <div class="card">
    <div class="card-header">
      <span class="logo cj">CJ온스타일</span>
      <span class="title" id="cj-title">{cj_tab or '홈 다음 탭'}</span>
      <span class="period" id="cj-period">{TODAY}</span>
    </div>
    <div class="card-body">
      <div class="screenshot-wrap">
        <p>모바일 캡처본</p>
        <img id="cj-img" src="captures/{latest}/cj_next_tab_full.png" alt="CJ온스타일" onclick="openModal(this.src)">
        <p style="font-size:10px;color:#bbb;">클릭하면 크게 보기</p>
      </div>
      <div class="summary" id="cj-summary">{cj_summary_txt}</div>
    </div>
  </div>
  <div class="card">
    <div class="card-header">
      <span class="logo lotte">롯데홈쇼핑</span>
      <span class="title" id="lotte-title">{lotte_tab or '홈 다음 탭'}</span>
      <span class="period" id="lotte-period">{TODAY}</span>
    </div>
    <div class="card-body">
      <div class="screenshot-wrap">
        <p>모바일 캡처본</p>
        <img id="lotte-img" src="captures/{latest}/lotte_next_tab_full.png" alt="롯데홈쇼핑" onclick="openModal(this.src)">
        <p style="font-size:10px;color:#bbb;">클릭하면 크게 보기</p>
      </div>
      <div class="summary" id="lotte-summary">{lotte_summary_txt}</div>
    </div>
  </div>
</div>
<div class="modal" id="modal" onclick="closeModal()">
  <span class="modal-close" onclick="closeModal()">✕</span>
  <img id="modal-img" src="" alt="">
</div>
<script>
  const summaries = {summaries_js};
  const NO_SUMMARY = '캡처 완료 — 행사 내용은 위 이미지를 확인하세요';
  function openModal(src) {{ document.getElementById('modal-img').src = src; document.getElementById('modal').classList.add('open'); }}
  function closeModal() {{ document.getElementById('modal').classList.remove('open'); }}
  function switchDate(d) {{
    document.getElementById('gs-img').src    = 'captures/' + d + '/gs_next_tab_full.png';
    document.getElementById('cj-img').src    = 'captures/' + d + '/cj_next_tab_full.png';
    document.getElementById('lotte-img').src = 'captures/' + d + '/lotte_next_tab_full.png';
    document.getElementById('gs-period').textContent    = d;
    document.getElementById('cj-period').textContent    = d;
    document.getElementById('lotte-period').textContent = d;
    document.getElementById('header-date').textContent  = '기준일: ' + d;
    document.querySelectorAll('.date-btn').forEach(b => b.classList.toggle('active', b.textContent === d));
    const s = summaries[d] || {{}};
    document.getElementById('gs-summary').textContent    = s.gs    || NO_SUMMARY;
    document.getElementById('cj-summary').textContent    = s.cj    || NO_SUMMARY;
    document.getElementById('lotte-summary').textContent = s.lotte  || NO_SUMMARY;
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
    files_to_add = [
        'index.html',
        f'{rel}/gs_next_tab_full.png',
        f'{rel}/cj_next_tab_full.png',
        f'{rel}/lotte_next_tab_full.png',
        f'{rel}/summary.json',
    ]
    cmds = [
        ['git', '-C', BASE_DIR, 'add', '--force'] + files_to_add,
        ['git', '-C', BASE_DIR, 'commit', '-m', f'Auto update: {TODAY}'],
        ['git', '-C', BASE_DIR, 'push', 'origin', 'main'],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout or result.stderr)


if __name__ == '__main__':
    print(f'[{TODAY}] 홈쇼핑 자동 캡처 시작...')

    archive_date_dir = os.path.join(ARCHIVE_DIR, TODAY_KEY)
    os.makedirs(archive_date_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        gs_tab = run_gs(browser, archive_date_dir)
        print(f'GS 완료: {gs_tab}')
        cj_tab = run_cj(browser, archive_date_dir)
        print(f'CJ 완료: {cj_tab}')
        lotte_tab = run_lotte(browser, archive_date_dir)
        print(f'롯데 완료: {lotte_tab}')
        browser.close()

    print('AI 요약 생성 중...')
    generate_summary(archive_date_dir, gs_tab, cj_tab, lotte_tab)

    archive_dates = get_archive_dates()
    update_html(gs_tab, cj_tab, lotte_tab, archive_dates)
    git_push(archive_date_dir)
    print('전체 완료! GitHub Pages 자동 업데이트됨')
