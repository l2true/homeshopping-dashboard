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


def generate_summary(archive_date_dir, cj_tab, lotte_tab):
    """Claude API로 캡처 이미지 분석 → 행사 요약 (ANTHROPIC_API_KEY 필요)"""
    try:
        import anthropic
    except ImportError:
        print('anthropic 미설치, 요약 건너뜀. pip install anthropic')
        return {}

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print('ANTHROPIC_API_KEY 없음, 요약 건너뜀')
        return {}

    client = anthropic.Anthropic()
    summaries = {}

    for brand, filename, label in [
        ('cj',    'cj_next_tab_full.png',    cj_tab    or 'CJ온스타일'),
        ('lotte', 'lotte_next_tab_full.png',  lotte_tab or '롯데홈쇼핑'),
    ]:
        img_path = os.path.join(archive_date_dir, filename)
        if not os.path.exists(img_path):
            summaries[brand] = '이미지 없음'
            continue

        with open(img_path, 'rb') as f:
            img_data = base64.standard_b64encode(f.read()).decode('utf-8')

        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1024,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {'type': 'base64', 'media_type': 'image/png', 'data': img_data},
                    },
                    {
                        'type': 'text',
                        'text': (
                            f'이 이미지는 {label} 탭의 모바일 홈쇼핑 캡처본입니다. '
                            '현재 진행 중인 주요 행사, 특가 상품, 기획전 등을 한국어로 간략히 요약해주세요. '
                            '3~5줄 이내로 핵심 내용만 정리해주세요.'
                        ),
                    },
                ],
            }],
        )
        summaries[brand] = resp.content[0].text
        print(f'{brand} 요약 완료')

    summary_path = os.path.join(archive_date_dir, 'summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    return summaries


def update_html(cj_tab, lotte_tab, archive_dates):
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
    cj_summary_txt   = latest_s.get('cj',    no_summary)
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
    .date-nav {{ max-width: 1400px; margin: 20px auto 0; padding: 0 24px; display: flex; gap: 8px; flex-wrap: wrap; }}
    .date-btn {{ padding: 6px 14px; border-radius: 20px; border: 1px solid #ddd; background: white; font-size: 13px; cursor: pointer; color: #555; }}
    .date-btn.active {{ background: #1a1a2e; color: white; border-color: #1a1a2e; font-weight: 700; }}
    .container {{ max-width: 1400px; margin: 20px auto 32px; padding: 0 24px; display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }}
    .card {{ background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; }}
    .card-header {{ padding: 20px 24px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #f0f0f0; }}
    .logo {{ font-size: 13px; font-weight: 800; padding: 6px 12px; border-radius: 8px; color: white; }}
    .logo.cj {{ background: #e8003d; }} .logo.lotte {{ background: #e60012; }}
    .card-header .title {{ font-size: 18px; font-weight: 700; }}
    .card-header .period {{ margin-left: auto; font-size: 13px; color: #888; background: #f5f5f5; padding: 4px 10px; border-radius: 20px; }}
    .card-body {{ display: flex; }}
    .screenshot-wrap {{ width: 200px; min-width: 200px; border-right: 1px solid #f0f0f0; padding: 16px; display: flex; flex-direction: column; align-items: center; gap: 8px; background: #fafafa; }}
    .screenshot-wrap p {{ font-size: 11px; color: #999; }}
    .screenshot-wrap img {{ width: 100%; border-radius: 8px; border: 1px solid #eee; cursor: pointer; transition: transform 0.2s; }}
    .screenshot-wrap img:hover {{ transform: scale(1.02); }}
    .summary {{ flex: 1; padding: 20px 24px; overflow-y: auto; max-height: 600px; font-size: 14px; line-height: 1.8; color: #444; white-space: pre-wrap; }}
    .summary.empty {{ display: flex; align-items: center; justify-content: center; color: #bbb; }}
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
    document.getElementById('cj-img').src   = 'captures/' + d + '/cj_next_tab_full.png';
    document.getElementById('lotte-img').src = 'captures/' + d + '/lotte_next_tab_full.png';
    document.getElementById('cj-period').textContent    = d;
    document.getElementById('lotte-period').textContent = d;
    document.getElementById('header-date').textContent  = '기준일: ' + d;
    document.querySelectorAll('.date-btn').forEach(b => b.classList.toggle('active', b.textContent === d));
    const s = summaries[d] || {{}};
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
        cj_tab = run_cj(browser, archive_date_dir)
        print(f'CJ 완료: {cj_tab}')
        lotte_tab = run_lotte(browser, archive_date_dir)
        print(f'롯데 완료: {lotte_tab}')
        browser.close()

    print('AI 요약 생성 중...')
    generate_summary(archive_date_dir, cj_tab, lotte_tab)

    archive_dates = get_archive_dates()
    update_html(cj_tab, lotte_tab, archive_dates)
    git_push(archive_date_dir)
    print('전체 완료! GitHub Pages 자동 업데이트됨')
