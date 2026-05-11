# -*- coding: utf-8 -*-
"""
홈쇼핑 일일 자동 캡처 & HTML 업데이트 스크립트
실행 시각: 매일 오전 10시 (Windows 작업 스케줄러)
"""

from playwright.sync_api import sync_playwright
from datetime import date
import os

BASE_DIR = r'C:\AI\claude_with_lakehouse'
TODAY = date.today().strftime('%Y.%m.%d')

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


def capture_full(page, filename):
    path = os.path.join(BASE_DIR, filename)
    page.screenshot(path=path, full_page=True)
    return path


def run_cj(browser):
    """CJ온스타일 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)

    # 홈 탭
    page.goto('https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005', wait_until='load', timeout=30000)
    page.wait_for_timeout(3000)
    close_popups(page)
    capture_full(page, 'cj_home_full.png')

    # 홈 오른쪽 탭 (쿠폰런 등 당일 탭)
    tab_name = click_next_tab(page)
    page.wait_for_timeout(2000)
    close_popups(page)
    capture_full(page, 'cj_next_tab_full.png')

    page.close()
    return tab_name


def run_lotte(browser):
    """롯데홈쇼핑 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)

    page.goto('https://m.lotteimall.com', wait_until='load', timeout=30000)
    page.wait_for_timeout(3000)
    close_popups(page)

    tab_name = click_next_tab(page)
    page.wait_for_timeout(2000)
    capture_full(page, 'lotte_next_tab_full.png')

    page.close()
    return tab_name


def update_html(cj_tab, lotte_tab):
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>홈쇼핑 행사 요약 — {TODAY}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; background: #f4f6f9; color: #222; }}
    header {{ background: #1a1a2e; color: white; padding: 24px 32px; display: flex; align-items: center; gap: 12px; }}
    header h1 {{ font-size: 20px; font-weight: 700; }}
    header span {{ font-size: 14px; color: #aaa; margin-left: auto; }}
    .container {{ max-width: 1400px; margin: 32px auto; padding: 0 24px; display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }}
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
    .summary {{ flex: 1; padding: 20px 24px; overflow-y: auto; max-height: 600px; display: flex; align-items: center; justify-content: center; color: #888; font-size: 14px; }}
    .modal {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 1000; justify-content: center; align-items: flex-start; padding: 24px; overflow-y: auto; }}
    .modal.open {{ display: flex; }}
    .modal img {{ max-width: 390px; width: 100%; border-radius: 12px; margin: auto; }}
    .modal-close {{ position: fixed; top: 16px; right: 20px; color: white; font-size: 32px; cursor: pointer; z-index: 1001; }}
    .notice {{ max-width: 1400px; margin: 0 auto 16px; padding: 0 24px; font-size: 13px; color: #999; }}
  </style>
</head>
<body>
<header>
  <h1>🛒 홈쇼핑 행사 요약</h1>
  <span>기준일: {TODAY} 오전 10시 자동 캡처</span>
</header>
<p class="notice">📌 행사 상세 분석은 Claude가 캡처 후 자동 생성합니다. 이미지를 클릭하면 크게 볼 수 있습니다.</p>
<div class="container">
  <div class="card">
    <div class="card-header">
      <span class="logo cj">CJ온스타일</span>
      <span class="title">{cj_tab or '홈 다음 탭'}</span>
      <span class="period">{TODAY}</span>
    </div>
    <div class="card-body">
      <div class="screenshot-wrap">
        <p>📱 모바일 캡처본</p>
        <img src="cj_next_tab_full.png" alt="CJ온스타일" onclick="openModal(this.src)">
        <p style="font-size:10px;color:#bbb;">클릭하면 크게 보기</p>
      </div>
      <div class="summary">캡처 완료 — 행사 내용은 위 이미지를 확인하세요</div>
    </div>
  </div>
  <div class="card">
    <div class="card-header">
      <span class="logo lotte">롯데홈쇼핑</span>
      <span class="title">{lotte_tab or '홈 다음 탭'}</span>
      <span class="period">{TODAY}</span>
    </div>
    <div class="card-body">
      <div class="screenshot-wrap">
        <p>📱 모바일 캡처본</p>
        <img src="lotte_next_tab_full.png" alt="롯데홈쇼핑" onclick="openModal(this.src)">
        <p style="font-size:10px;color:#bbb;">클릭하면 크게 보기</p>
      </div>
      <div class="summary">캡처 완료 — 행사 내용은 위 이미지를 확인하세요</div>
    </div>
  </div>
</div>
<div class="modal" id="modal" onclick="closeModal()">
  <span class="modal-close" onclick="closeModal()">✕</span>
  <img id="modal-img" src="" alt="">
</div>
<script>
  function openModal(src) {{ document.getElementById('modal-img').src = src; document.getElementById('modal').classList.add('open'); }}
  function closeModal() {{ document.getElementById('modal').classList.remove('open'); }}
</script>
</body>
</html>"""

    with open(os.path.join(BASE_DIR, 'event_summary.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'HTML 업데이트 완료: {TODAY}')


if __name__ == '__main__':
    print(f'[{TODAY}] 홈쇼핑 자동 캡처 시작...')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        cj_tab = run_cj(browser)
        print(f'CJ 완료: {cj_tab}')
        lotte_tab = run_lotte(browser)
        print(f'롯데 완료: {lotte_tab}')
        browser.close()
    update_html(cj_tab, lotte_tab)
    print('전체 완료!')
