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
DEVICE_SCALE = 2   # 캡처 해상도 배율 (작은 글씨/숫자 판독 정확도 향상)


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


NOISE_TABS = {'팝업 닫기', '위로 가기', '고객센터', '로그인', '홈화면', '카테고리', '마이페이지', '최근본쇼핑', '홈 바로가기'}

def get_all_tabs(page, home_label='홈'):
    """탭바에서 홈 탭 기준으로 보이는 탭명 전체 목록 반환
    - 줄바꿈 탭(예: 7%+13%\\n뷰티페스타)은 마지막 줄(실제 탭명)만 사용
    - 중복·노이즈 제거, 최대 12개 제한
    """
    try:
        tabs = page.evaluate("""
            (homeLabel) => {
                const tabs = Array.from(document.querySelectorAll('.tab_menu a, .gnb_menu a, [class*=tab] a'));
                const homeIdx = tabs.findIndex(a => a.innerText.trim() === homeLabel);
                if (homeIdx < 0) return [];
                const seen = new Set();
                const result = [];
                for (const a of tabs.slice(homeIdx)) {
                    const lines = a.innerText.trim().split('\\n').map(l => l.trim()).filter(l => l);
                    // 줄바꿈 있으면 마지막 줄이 실제 탭명 (첫 줄은 할인율 등 부가정보)
                    const t = lines.length > 1 ? lines[lines.length - 1] : (lines[0] || '');
                    if (!t) continue;
                    if (seen.has(t)) break;  // 중복 시작 = 본문 링크 진입, 중단
                    seen.add(t);
                    result.push(t);
                    if (result.length >= 12) break;
                }
                return result;
            }
        """, home_label)
        # 노이즈 탭 필터링 (팝업 닫기, 로그인 등 UI 요소)
        return [t for t in tabs if t not in NOISE_TABS and len(t) < 30
                and '공지사항' not in t and '처리방침' not in t]
    except:
        return []


def save_tab_names(archive_dir, brand, tabs):
    """tab_names.json에 해당 브랜드 탭 목록 기록 (누적)"""
    path = os.path.join(archive_dir, 'tab_names.json')
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {}
    # 이모지 등 cp949 비호환 문자 제거 후 저장
    data[brand] = [t.encode('utf-8', errors='replace').decode('utf-8') for t in (tabs or [])]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def click_next_tab(page, home_label='홈', skip_labels=None):
    """홈 탭 오른쪽 탭 클릭 (home_label: 홈 탭 텍스트)
    skip_labels: 해당 탭명이 포함되면 한 칸 더 오른쪽으로 이동 (예: CJ 라이브쇼특가)
    """
    return page.evaluate("""
        ([homeLabel, skipLabels]) => {
            const tabs = Array.from(document.querySelectorAll('.tab_menu a, .gnb_menu a, [class*=tab] a'));
            const homeIdx = tabs.findIndex(a => a.innerText.trim() === homeLabel);
            if (homeIdx < 0) return null;
            let nextIdx = homeIdx + 1;
            if (nextIdx < tabs.length && skipLabels && skipLabels.length > 0) {
                const nextText = tabs[nextIdx].innerText.trim();
                const shouldSkip = skipLabels.some(s => nextText.includes(s));
                if (shouldSkip && nextIdx + 1 < tabs.length) {
                    nextIdx = nextIdx + 1;
                }
            }
            if (nextIdx < tabs.length) {
                tabs[nextIdx].click();
                return tabs[nextIdx].innerText.trim();
            }
            return null;
        }
    """, [home_label, skip_labels or []])


def scroll_to_load(page, steps=6, delay_ms=300):
    """lazy-load 트리거: 단계적 스크롤 후 맨 위로 복귀"""
    total = page.evaluate("document.body.scrollHeight")
    for i in range(1, steps + 1):
        page.evaluate(f"window.scrollTo(0, {int(total * i / steps)})")
        page.wait_for_timeout(delay_ms)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)


def capture_full(page, path):
    # document.fonts.ready 오버라이드 → 폰트 로딩 대기로 인한 타임아웃 방지
    try:
        page.evaluate("""
            () => {
                try {
                    Object.defineProperty(document.fonts, 'ready', {
                        get: () => Promise.resolve(document.fonts),
                        configurable: true
                    });
                } catch(e) {}
            }
        """)
    except Exception:
        pass
    try:
        page.screenshot(path=path, full_page=True, timeout=60000, animations='disabled')
    except Exception:
        # fallback: 실제 콘텐츠 높이만큼 뷰포트 조정 후 캡처
        total_h = page.evaluate("""
            () => Math.max(
                document.body.scrollHeight,
                document.documentElement.scrollHeight
            )
        """) or 6000
        page.set_viewport_size({'width': VIEWPORT['width'], 'height': min(int(total_h), 15000)})
        page.wait_for_timeout(300)
        page.screenshot(path=path, full_page=False, timeout=30000, animations='disabled')
        page.set_viewport_size(VIEWPORT)
    # 하단 흰 여백 제거 (scrollHeight 과대산정으로 인한 빈 공간 크롭)
    _crop_white_bottom(path)
    return path


def _crop_white_bottom(path, threshold=250):
    """이미지 하단의 흰색 여백을 제거한다."""
    try:
        from PIL import Image
        import numpy as np
        img = Image.open(path).convert('RGB')
        arr = np.array(img)
        # 각 행의 최솟값이 threshold 이상이면 흰색 행으로 판단
        row_min = arr.min(axis=(1, 2))
        non_white = np.where(row_min < threshold)[0]
        if len(non_white) == 0:
            return
        last_row = int(non_white[-1]) + 1
        if last_row < img.height:
            img.crop((0, 0, img.width, last_row)).save(path)
    except Exception:
        pass


def capture_banner(page, path, height=600):
    """상단 배너 영역만 크롭 저장 (메인 프로모션명 판독용)"""
    page.screenshot(path=path, clip={'x': 0, 'y': 0, 'width': VIEWPORT['width'], 'height': height},
                    timeout=60000, animations='disabled')
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
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA, device_scale_factor=DEVICE_SCALE)
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
    # 현대홈쇼핑 다음 이벤트 탭 URL을 추출해 직접 이동
    # (탭 클릭 방식은 SPA가 서브탭을 자동 선택해 이벤트 랜딩 사라짐)
    event_info = page.evaluate("""
        () => {
            const tabs = Array.from(document.querySelectorAll('[data-maindispseq]'));
            const idx = tabs.findIndex(el =>
                (el.getAttribute('data-appmaincallurl') || '').includes('frstDispTryNmCd=newHome')
            );
            if (idx < 0 || idx + 1 >= tabs.length) return null;
            const next = tabs[idx + 1];
            const callUrl = next.getAttribute('data-appmaincallurl') || '';
            const name = (next.getAttribute('data-rel') || next.innerText || '').trim().split('\\n').join(' ');
            return {url: callUrl ? 'https://www.hmall.com' + callUrl : null, name: name};
        }
    """)
    tab_name = None
    if event_info and event_info.get('url'):
        tab_name = event_info['name']
        page.goto(event_info['url'], wait_until='domcontentloaded', timeout=30000)
    save_tab_names(archive_dir, 'hyundai', [tab_name] if tab_name else [])
    page.wait_for_timeout(2500)
    close_popups(page)
    scroll_to_load(page)
    capture_full(page, os.path.join(archive_dir, 'hyundai_next_tab_full.png'))
    capture_banner(page, os.path.join(archive_dir, 'hyundai_banner.png'))
    save_page_text(page, os.path.join(archive_dir, 'hyundai_page_text.txt'))
    page.close()
    return tab_name


def _run_with_retry(func, browser, archive_dir, retries=1):
    """캡처 함수 실패 시 재시도 (최대 retries회)"""
    last_err = None
    for attempt in range(retries + 1):
        try:
            return func(browser, archive_dir)
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(f'  재시도 {attempt+1}/{retries}: {e}')
    raise last_err


def run_gs(browser, archive_dir):
    """GS SHOP 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA, device_scale_factor=DEVICE_SCALE)
    # 폰트 로딩이 스크린샷을 무한 대기시키는 문제 방지
    page.route('**/*.{woff,woff2,ttf,otf,eot}', lambda route: route.abort())
    page.goto('https://m.gsshop.com', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(3000)
    close_popups_gs(page)
    page.wait_for_timeout(1000)
    close_popups_gs(page)
    # GS는 nav a 셀렉터 사용 (기존 [class*=tab] 셀렉터와 다름)
    tab_name = page.evaluate("""
        () => {
            const nav = document.querySelector('#main_tab_list, nav[id*=tab], nav');
            if (!nav) return null;
            const tabs = Array.from(nav.querySelectorAll('a'));
            // class="home" 우선, 없으면 텍스트로 fallback
            const homeIdx = tabs.findIndex(a =>
                a.classList.contains('home') ||
                a.innerText.trim().split('\\n')[0].trim() === '홈'
            );
            if (homeIdx < 0) return null;
            const next = tabs[homeIdx + 1];
            if (!next) return null;
            next.click();
            const span = next.querySelector('span');
            return (span ? span.innerText : next.innerText).trim();
        }
    """)
    save_tab_names(archive_dir, 'gs', [tab_name] if tab_name else [])
    page.wait_for_timeout(3000)
    try:
        page.wait_for_load_state('networkidle', timeout=8000)
    except: pass
    close_popups_gs(page)
    scroll_to_load(page)
    # viewport를 콘텐츠 높이로 확장 후 재렌더링 대기 → 전체 캡처
    loaded_h = page.evaluate("document.documentElement.scrollHeight") or 6000
    capped_h = min(int(loaded_h), 8000)
    page.set_viewport_size({'width': VIEWPORT['width'], 'height': capped_h})
    page.wait_for_timeout(1500)
    # 재렌더링 후 추가 콘텐츠 로드 트리거
    scroll_to_load(page, steps=4, delay_ms=200)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(800)
    page.screenshot(path=os.path.join(archive_dir, 'gs_next_tab_full.png'),
                    full_page=False, timeout=30000, animations='disabled')
    capture_banner(page, os.path.join(archive_dir, 'gs_banner.png'))
    save_page_text(page, os.path.join(archive_dir, 'gs_page_text.txt'))
    page.close()
    return tab_name


CJ_SKIP_TABS = ['라이브쇼특가', '매일특가']        # CJ: 홈 바로 옆이 이 탭이면 그 다음 탭으로 이동
HYUNDAI_SKIP_TABS = ['오감쇼']                    # 현대: 방송 프로그램 탭 스킵 → 피드백 시 추가

def run_cj(browser, archive_dir):
    """CJ온스타일 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA, device_scale_factor=DEVICE_SCALE)
    page.goto('https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)
    close_popups(page)
    save_tab_names(archive_dir, 'cj', get_all_tabs(page))
    tab_name = click_next_tab(page, skip_labels=CJ_SKIP_TABS)
    page.wait_for_timeout(2000)
    close_popups(page)
    scroll_to_load(page)
    capture_full(page, os.path.join(archive_dir, 'cj_next_tab_full.png'))
    capture_banner(page, os.path.join(archive_dir, 'cj_banner.png'))
    save_page_text(page, os.path.join(archive_dir, 'cj_page_text.txt'))
    page.close()
    return tab_name


def close_popups_lotte(page):
    """롯데홈쇼핑 전용 팝업 닫기"""
    close_popups(page)
    # "오늘 그만 보기" 우선, 없으면 "닫기"
    for text in ['오늘 그만 보기', '닫기', '오늘하루 보지않기']:
        try:
            page.get_by_text(text, exact=True).first.click(timeout=2000)
            page.wait_for_timeout(400)
        except: pass
    for sel in ['.btn_layer_close', '.popup_close', '.layer_close',
                '.pop_close', '.btn_close', '[class*=popup] [class*=close]',
                '[class*=layer] [class*=close]']:
        try:
            for btn in page.locator(sel).all():
                if btn.is_visible():
                    btn.click(timeout=1000)
                    page.wait_for_timeout(300)
        except: pass


def run_lotte(browser, archive_dir):
    """롯데홈쇼핑 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA, device_scale_factor=DEVICE_SCALE)
    page.goto('https://m.lotteimall.com', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)
    close_popups_lotte(page)
    page.wait_for_timeout(500)
    close_popups_lotte(page)  # 2차 시도
    save_tab_names(archive_dir, 'lotte', get_all_tabs(page))
    tab_name = click_next_tab(page)
    page.wait_for_timeout(2000)
    close_popups_lotte(page)  # 탭 전환 후 팝업 재확인
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
        capture_output=True, env=env, timeout=300,
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
    """요약 텍스트에서 기간/프로모션명/혜택 본문 분리.
    '---' 이후의 Claude 부가 설명은 제거한다.
    """
    period, name, body_lines = '', '', []
    for line in text.strip().splitlines():
        # --- 구분선 이후는 Claude 설명 → 무시
        if line.strip().startswith('---'):
            break
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
    '카드 할인, 적립, 쿠폰 등 구체적인 혜택이 하나도 없는 단순 방송 홍보(예: 오감쇼, 스페셜방송 등)도 '
    '"해당없음"으로 처리하세요. 혜택 항목을 작성할 수 없으면 반드시 "해당없음"입니다. '
    '페이지 텍스트에 없더라도 이미지에서 보이는 혜택은 반드시 추출하세요. '
    '구매 사은품(증정품), 쇼핑 지원금, 선착순 증정 등도 이미지에서 확인되면 사은품 또는 쿠폰으로 작성하세요. '
    '현대홈쇼핑 행사는 여러 섹션으로 구성되어 있습니다. 다음 항목을 빠짐없이 확인하세요: '
    '① TV상품 구매 혜택(적립·카드할인·구매 사은품) '
    '② 매일 이벤트(룰렛·소문내기·출석체크 등 경품 이벤트) '
    '③ 더드림 브랜드 특가(브랜드별 중복혜택·할인율) '
    '④ 기타 쿠폰·적립 혜택. '
    '각 섹션에서 확인된 혜택을 모두 추출하세요.'
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
        capture_date_str = os.path.basename(archive_date_dir)  # YYYY-MM-DD
        prompt = (
            f'{label} 홈쇼핑 모바일 캡처본입니다. 캡처 날짜: {capture_date_str}\n'
            '텍스트 원문을 우선 참고하되, 텍스트에 없더라도 이미지에서 명확히 보이는 혜택(사은품, 쿠폰, 적립 등)은 반드시 함께 추출하세요.\n\n'
            + (extra + '\n\n' if extra else '') +
            '규칙:\n'
            '- **, ##, --- 등 마크다운 기호 절대 사용 금지\n'
            '- 부연 설명, 안내 문구 추가 금지\n'
            '- 확인되지 않는 항목은 행 자체를 생략\n'
            '- 행사 대표 혜택만 추출하세요. 상단 배너·"주요 혜택 모아보기" 같은 행사 전체 공통 혜택 영역에 있는 것만 채택합니다. '
            '개별 상품 카드에 붙은 뱃지(예: "오늘만10%적립+10%카드", "쿠폰24%")처럼 특정 상품에만 적용되는 혜택은 행사 대표 혜택이 아니므로 제외하세요.\n\n'
            '형식:\n'
            '기간: (행사 기간)\n'
            '프로모션명: (메인 행사명 하나만, 서브 행사명 나열 금지. 페이지에 명확한 행사명이 있으면 그대로 사용, 없으면 배너 로고 텍스트를 활용)\n'
            '혜택:\n'
            '  혜택종류: 혜택상세\n\n'
            '기간 작성 규칙:\n'
            '- 반드시 "M/DD ~ M/DD" 형식으로 작성 (예: 5/13 ~ 5/17)\n'
            '- 종료일만 알면 "~ M/DD" 형식으로 작성\n'
            '- 날짜를 전혀 확인할 수 없으면 기간 행 자체를 생략\n'
            '- "상반기", "기간 미확인" 등 모호한 표현 절대 금지\n\n'
            '혜택종류는 반드시 카드, 적립, 사은품, 경품, 할인, 특가, 쿠폰 중에서만 선택하세요. 그 외 표현(하루만혜택, 단독, 오늘만 등)은 특가로 통일하세요.\n'
            '혜택상세에는 혜택 내용과 함께 적용 조건(선착순 인원, 최대 금액, 기간 등)을 적어주세요.\n'
            '카드 혜택은 특정 카드사명(삼성카드, KB카드, 현대카드 등)을 절대 기재하지 마세요. '
            '카드사는 매일 바뀌므로 "카드: 7% 할인" 또는 "카드: 최대 7% 할인" 형식으로만 작성하세요 (뒤에 반드시 할인 포함). 즉시할인/청구할인 등 할인 방식은 절대 쓰지 마세요.\n'
            '혜택이 여러 개면 줄을 나눠 작성하되, 같은 혜택종류는 반드시 하나로 묶어 작성하세요.\n'
            '①②③ 또는 혜택1·2·3처럼 단계별로 나뉜 쿠폰/할인은 절대 여러 줄로 쓰지 말고 "최대 N% (A·B·C% 선택)" 형식으로 한 줄에 작성하세요.\n'
            '예) 특가가 여러 브랜드에 걸쳐 있으면: "특가: 최대 85% 할인 (나인식스뉴욕·아디다스·MLB 등)"\n'
            '긴 기간 행사에서 날짜별 세부 일정이 보이면(예: 적립 캘린더, 일별 카테고리 등) '
            f'캡처 날짜({capture_date_str})에 해당하는 혜택을 우선 추출하세요. '
            '예) "6.1-6.2 리빙, 6.3-6.4 식품" 형식이면 해당 날짜의 카테고리만 기재.\n'
            '브랜드를 개별 나열하지 말고 최대 혜택값과 대표 브랜드 2~3개만 표기하세요. 혜택 줄 수는 최대 5줄.'
        )
        text_path   = img_path.replace('_next_tab_full.png', '_page_text.txt')
        banner_path = img_path.replace('_next_tab_full.png', '_banner.png')
        try:
            raw = _ask_claude(img_path, prompt, text_path, banner_path)
            result = parse_summary_text(raw)
            # 현대: 혜택(body)이 없으면 단순 방송 홍보 → 해당없음 강제 처리
            if brand == 'hyundai' and not result.get('body', '').strip():
                result = {'period': '', 'name': '해당없음', 'body': ''}
            summaries[brand] = result
            print(f'{brand} 요약 완료')
        except Exception as e:
            print(f'{brand} 요약 실패: {e}')
            summaries[brand] = {'period': '', 'name': '', 'body': '요약 생성 실패'}

    update_promo_start(summaries)

    summary_path = os.path.join(archive_date_dir, 'summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    # 배너 크롭은 날짜 파악용으로만 사용 → 요약 완료 후 삭제
    for banner in glob.glob(os.path.join(archive_date_dir, '*_banner.png')):
        try:
            os.remove(banner)
            print(f'배너 삭제: {os.path.basename(banner)}')
        except Exception as e:
            print(f'배너 삭제 실패: {e}')

    return summaries


import re as _re_module
_CARD_NAMES = _re_module.compile(
    r'(삼성|현대|KB국민|국민|신한|롯데|하나|우리|NH농협|농협|씨티|토스|카카오|BC|IBK기업|기업|수협|광주|전북|제주|산업|우체국)\s*카드\s*'
)

def _clean_card_detail(detail: str) -> str:
    """카드 혜택 상세에서 특정 카드사명 제거"""
    cleaned = _CARD_NAMES.sub('카드 ', detail).strip()
    cleaned = _re_module.sub(r'카드\s+카드', '카드', cleaned).strip()
    return cleaned


def validate_periods(gap_days=21):
    """period 종료일이 그 행사가 실제 등장한 마지막 날보다 gap_days 이상 뒤면
    날짜 오독(예: 6/24를 8/24로 읽음) 가능성이 높으므로 로그에 경고를 남긴다.
    자동 수정은 하지 않는다 (실제로 긴 행사일 수 있으므로 사람이 확인)."""
    from datetime import datetime, timedelta
    chans = ['hyundai', 'gs', 'cj', 'lotte']
    appear = {}   # (ch, name) -> [dates]
    rows = {}     # date -> data
    for d in sorted(glob.glob(os.path.join(ARCHIVE_DIR, '????-??-??'))):
        date = os.path.basename(d)
        p = os.path.join(d, 'summary.json')
        if not os.path.exists(p):
            continue
        try:
            data = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        rows[date] = data
        for ch in chans:
            n = (data.get(ch, {}).get('name') or '').strip()
            if n and n != '해당없음':
                appear.setdefault((ch, n), []).append(date)

    def period_end(period, refdate):
        mds = _re_module.findall(r'\d{1,2}/\d{1,2}', period or '')
        if not mds:
            return None
        mo, da = map(int, mds[-1].split('/'))
        ry = int(refdate[:4])
        sd = datetime.strptime(refdate, '%Y-%m-%d')
        end = datetime(ry, mo, da)
        if end < sd - timedelta(days=180):
            end = datetime(ry + 1, mo, da)
        return end

    warned = 0
    seen = set()
    for date in sorted(rows):
        for ch in chans:
            s = rows[date].get(ch, {})
            n = (s.get('name') or '').strip()
            period = (s.get('period') or '').strip()
            if not n or n == '해당없음' or not period:
                continue
            key = (ch, n, period)
            if key in seen:
                continue
            seen.add(key)
            pe = period_end(period, date)
            if not pe:
                continue
            last = max(appear.get((ch, n), [date]))
            gap = (pe - datetime.strptime(last, '%Y-%m-%d')).days
            if gap > gap_days:
                warned += 1
                print(f'  [기간검증] (!) [{ch}] {n!r} period={period!r} '
                      f'종료일={pe.date()} 마지막등장={last} (+{gap}일) -> 날짜 오독 의심')
    if warned == 0:
        print('  [기간검증] 이상 없음')
    return warned


def consolidate_ongoing_events():
    """같은 행사가 여러 날 걸쳐 있을 때, 날짜별 캡처 품질 차이를 보완.
    동일 브랜드+start 날짜 기준으로 모든 날짜의 혜택 줄을 통합해
    가장 완전한 요약본으로 전체 날짜를 일괄 업데이트한다.
    """
    from collections import defaultdict, OrderedDict

    # 1. 전체 날짜의 summary.json 로드
    all_summaries = {}  # {date: {brand: {...}}}
    for d in sorted(glob.glob(os.path.join(ARCHIVE_DIR, '????-??-??'))):
        date_key = os.path.basename(d)
        path = os.path.join(d, 'summary.json')
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding='utf-8') as f:
                all_summaries[date_key] = json.load(f)
        except Exception:
            continue

    if not all_summaries:
        return

    # 이름 정규화: 채널명 prefix 제거 + 공백 제거
    _PREFIX = _re_module.compile(r'^(GS샵?|CJ온스타일|롯데홈쇼핑|현대홈쇼핑|현대Hmall|GS SHOP)\s*', _re_module.IGNORECASE)
    def _norm_name(n):
        return _PREFIX.sub('', n).strip().replace(' ', '').lower()

    # 2. 브랜드별로 정규화된 이름 기준 그룹화 (start가 달라도 같은 행사명이면 통합)
    # event_key → [(date, body, period, start), ...]
    event_groups = defaultdict(list)
    for date, summaries in all_summaries.items():
        for brand, s in summaries.items():
            if not isinstance(s, dict):
                continue
            name = s.get('name', '').strip()
            start = s.get('start', '').strip()
            body = s.get('body', '').strip()
            if not name or name in ('해당없음', '요약 생성 실패'):
                continue
            norm = _norm_name(name)
            event_groups[(brand, norm)].append((date, body, s.get('period', ''), start, name))

    # 2-1. 연속성 가드: 같은 행사명이라도 캡처 날짜가 MAX_GAP_DAYS 초과로 끊기면 별개 행사로 분리.
    # (푸드페스타·매직딜데이처럼 주기적으로 반복되는 행사가 과거 것과 엉겨붙는 것을 방지)
    from datetime import datetime as _dtm
    MAX_GAP_DAYS = 3
    run_groups = defaultdict(list)
    for (brand, norm), ents in event_groups.items():
        ents.sort(key=lambda e: e[0])  # 날짜순
        run_idx = 0
        prev_d = None
        for e in ents:
            d = _dtm.strptime(e[0], '%Y-%m-%d')
            if prev_d is not None and (d - prev_d).days > MAX_GAP_DAYS:
                run_idx += 1  # 간격이 벌어지면 새 행사 구간
            run_groups[(brand, norm, run_idx)].append(e)
            prev_d = d
    event_groups = run_groups

    # 3. 2일 이상 이어지는 행사만 통합
    # 단, 날짜별로 혜택이 의도적으로 다른 행사(적립 카테고리가 매일 다른 경우 등)는 제외
    updated = 0
    for (brand, norm, _run), entries in event_groups.items():
        if len(entries) < 2:
            continue
        # 동일 혜택종류에 3가지 이상 서로 다른 내용이 있으면 날짜별 의도 변화 → skip
        from collections import defaultdict as _dd
        type_details = _dd(set)
        for _, body, _, _, _ in entries:
            for line in body.split('\n'):
                t = line.strip()
                if ':' in t and not t.startswith('혜택'):
                    btype, _, detail = t.partition(':')
                    type_details[btype.strip()].add(detail.strip())
        if any(len(v) >= 3 for v in type_details.values()):
            continue  # 날짜별로 내용이 3가지 이상 다름 → consolidate 안 함

        # 가장 많이 등장한 이름 + 가장 이른 start 선택
        from collections import Counter
        name_counts = Counter(e[4] for e in entries)
        best_name = name_counts.most_common(1)[0][0]
        starts = [e[3] for e in entries if e[3]]
        best_start = min(starts) if starts else ''

        # 모든 날짜의 혜택 줄 수집 → 혜택종류별 unique detail
        benefit_map = OrderedDict()
        for _, body, _, _, _ in entries:
            for line in body.split('\n'):
                t = line.strip()
                if not t or t == '혜택:':
                    continue
                if ':' in t:
                    btype, _, detail = t.partition(':')
                    btype = btype.strip()
                    detail = detail.strip()
                    _VALID_TYPES = {'카드','적립','사은품','경품','할인','특가','쿠폰'}
                if btype and detail:
                        if btype == '카드':
                            detail = _clean_card_detail(detail)
                        if btype not in _VALID_TYPES:
                            btype = '특가'  # 비표준 혜택종류 → 특가로 통일
                        if btype not in benefit_map:
                            benefit_map[btype] = []
                        if detail not in benefit_map[btype]:
                            benefit_map[btype].append(detail)

        if not benefit_map:
            continue

        # 통합 body 생성 — 이미 묶인 요약(·, 등 포함)을 우선 선택, 없으면 가장 짧은 것
        lines = ['혜택:']
        for btype, details in benefit_map.items():
            aggregated = [d for d in details if '·' in d or d.endswith('등)') or d.endswith('등')]
            if aggregated:
                best = max(aggregated, key=len)  # 묶인 것 중 가장 정보 많은 것
            else:
                best = min(details, key=len)     # 아니면 가장 간결한 것
            lines.append(f'  {btype}: {best}')
        consolidated_body = '\n'.join(lines)

        # 날짜 형식인 period만 후보로 — "5/25 ~ 6/7" 같이 숫자/슬래시/물결 포함
        valid_periods = [e[2] for e in entries if e[2] and _re_module.search(r'\d+/\d+', e[2])]
        best_period = max(valid_periods, key=len, default='')

        # 4. 해당 행사 모든 날짜 업데이트 (이름·start·period·body 모두 통일)
        changed_dates = []
        for date, body, period, start, name in entries:
            needs_update = (
                body != consolidated_body or
                name != best_name or
                start != best_start or
                (best_period and period != best_period)
            )
            if not needs_update:
                continue
            path = os.path.join(ARCHIVE_DIR, date, 'summary.json')
            try:
                with open(path, encoding='utf-8') as f:
                    s = json.load(f)
                s[brand]['name'] = best_name
                s[brand]['start'] = best_start
                s[brand]['body'] = consolidated_body
                if best_period:
                    s[brand]['period'] = best_period
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(s, f, ensure_ascii=False, indent=2)
                changed_dates.append(date)
                updated += 1
            except Exception as e:
                print(f'  consolidate 실패 {date}/{brand}: {e}')

        if changed_dates:
            print(f'  [{brand}] {best_name} ({best_start}~) → {len(changed_dates)}일 통합 업데이트')

    print(f'consolidate 완료: {updated}건 업데이트')


def _normalize_date(s):
    """날짜 문자열을 M/DD 형식으로 정규화
    입력 예: '05-12', '5.12', '5/12', '2026-05-12' → '5/12'
    """
    import re
    s = s.strip()
    # YYYY-MM-DD 또는 YYYY.MM.DD
    m = re.fullmatch(r'\d{4}[-./](\d{1,2})[-./](\d{1,2})', s)
    if m:
        return f'{int(m.group(1))}/{m.group(2).zfill(2)}'
    # MM-DD 또는 MM.DD 또는 M/DD 등
    m = re.fullmatch(r'(\d{1,2})[-./](\d{1,2})', s)
    if m:
        return f'{int(m.group(1))}/{m.group(2).zfill(2)}'
    return s


def _extract_end_date(period):
    """기간 문자열에서 끝날짜만 추출 (숫자가 포함된 경우만 유효로 판단)"""
    import re
    if '~' in period:
        end = period.split('~')[-1].strip()
    elif ' - ' in period or '–' in period:
        end = re.split(r' - |–', period)[-1].strip()
    else:
        return None
    if re.search(r'\d{1,4}[./-]\d{1,2}', end):
        return _normalize_date(end)
    return None


def _fmt_start(start_iso):
    """YYYY-MM-DD → M/DD 형식으로 변환"""
    return _normalize_date(start_iso)


def _s(brand_data, key, fallback=''):
    """summary dict 또는 구버전 string 에서 값 추출"""
    if not isinstance(brand_data, dict):
        return fallback if key != 'body' else str(brand_data)
    if key == 'period':
        start = brand_data.get('start', '')
        period = brand_data.get('period', '')
        import re
        end = _extract_end_date(period) if period else None
        # AI가 시작일도 알고 있으면(period에 ~ 앞부분이 날짜이면) 그대로 사용
        period_has_start = bool(period and '~' in period and re.search(r'\d{1,4}[./-]\d{1,2}', period.split('~')[0]))
        if period_has_start and end:
            ai_start = _normalize_date(period.split('~')[0].strip())
            return f'{ai_start} ~ {end}'
        # AI가 시작일 모르면 tracking start + AI 끝날짜
        if start and end:
            return f'{_fmt_start(start)} ~ {end}'
        # 끝날짜도 없으면: period가 "매주 화요일" 같은 텍스트이면 그대로, 아니면 start
        if period and not re.fullmatch(r'[\d./-]+', period.strip()):
            return period  # 텍스트 형태 기간은 그대로
        if start:
            return _fmt_start(start)
        return period or fallback
    return brand_data.get(key, fallback)


SCHEDULE_TEMPLATE = r'''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>홈쇼핑 프로모션 편성표</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; background: #f4f6f9; color: #222; }
    header { background: white; color: #1a1a2e; padding: 18px 32px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; box-shadow: 0 1px 0 #ebebf0; }
    header h1 { font-size: 20px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.2; }
    .header-sub { font-size: 10px; color: #bbb; font-weight: 500; letter-spacing: 2px; margin-top: 3px; }
    .top-nav { display: flex; gap: 8px; }
    .top-nav a { font-size: 13px; font-weight: 700; color: #888; text-decoration: none; padding: 7px 16px; border-radius: 20px; transition: all 0.15s; }
    .top-nav a:hover { background: #f0f4ff; color: #1a1a2e; }
    .top-nav a.active { background: #1a1a2e; color: white; }
    .header-right { font-size: 11px; color: #888; }
    .header-bar { height: 3px; background: linear-gradient(to right, #9dc3e8 25%, #cdb3e6 25% 50%, #e8a9a9 50% 75%, #efc199 75%); position: sticky; top: 57px; z-index: 99; }
    .sched-wrap { padding: 20px; }
    .filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
    .filters .flabel { font-size: 12px; font-weight: 700; color: #999; margin-right: 4px; }
    .fchip { font-size: 12px; font-weight: 700; color: #666; background: white; border: 1px solid #e0e4ff; padding: 7px 14px; border-radius: 20px; cursor: pointer; transition: all 0.15s; }
    .fchip:hover { background: #f0f4ff; }
    .fchip.active { background: #1a1a2e; color: white; border-color: #1a1a2e; }
    .week-nav { display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 18px; position: relative; }
    .week-nav button { background: white; border: 1px solid #e0e4ff; color: #444; font-size: 13px; font-weight: 600; padding: 8px 14px; border-radius: 8px; cursor: pointer; transition: all 0.15s; }
    .week-nav button:hover { background: #f0f4ff; }
    .week-nav #week-label { font-size: 16px; font-weight: 800; color: #1a1a2e; min-width: 150px; text-align: center; letter-spacing: 0.3px; cursor: pointer; background: white; border: 1px solid #e0e4ff; border-radius: 8px; padding: 8px 18px; }
    .week-nav #week-label:hover { background: #f0f4ff; }
    .cal-pop { display: none; position: absolute; top: 46px; left: 50%; transform: translateX(-50%); z-index: 200; background: white; border: 1px solid #e0e4ff; border-radius: 12px; padding: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); min-width: 280px; }
    .cal-pop.open { display: block; }
    .cal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
    .cal-head button { background: none; border: none; cursor: pointer; font-size: 14px; padding: 2px 10px; color: #555; }
    .cal-head span { font-size: 13px; font-weight: 700; }
    .cal-table { width: 100%; border-collapse: separate; border-spacing: 2px; }
    .cal-table th { font-size: 10px; color: #aaa; font-weight: 600; padding: 2px 0; }
    .cal-table td { text-align: center; padding: 6px 2px; border-radius: 7px; font-size: 13px; cursor: pointer; }
    .cal-table td.has { color: #333; font-weight: 600; }
    .cal-table td.no { color: #ccc; }
    .cal-table td.inweek { background: #eef2ff; }
    .cal-table td.today { outline: 2px solid #c62828; }
    .cal-table td:hover { background: #1a1a2e; color: white; }
    .gantt { background: white; border-radius: 14px; padding: 6px 10px 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); overflow-x: auto; }
    .g-row { display: flex; align-items: stretch; }
    .ch-label { width: 92px; min-width: 92px; color: white; font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; border-radius: 9px; margin: 4px 8px 4px 0; }
    .ch-label.head { background: transparent; }
    .g-head .track { display: flex; height: 44px; }
    .g-head .dcol { flex: 1; text-align: center; border-left: 1px solid #f0f0f2; display: flex; flex-direction: column; justify-content: center; }
    .g-head .dcol.today .d-date { color: #c62828; }
    .g-head .dcol .d-date { font-size: 13px; font-weight: 800; color: #444; }
    .g-head .dcol .d-dow { font-size: 10px; color: #aaa; margin-top: 2px; }
    .track { position: relative; flex: 1; min-width: 420px; }
    .gline { position: absolute; top: 0; bottom: 0; width: 1px; background: #f0f0f2; }
    .gline.today { background: #fbcfc4; width: 2px; }
    .bar { position: absolute; height: 26px; border-radius: 7px; font-size: 11.5px; font-weight: 700; line-height: 24px; padding: 0 9px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; cursor: default; transition: opacity 0.15s; }
    .bar.cl { border-top-left-radius: 0; border-bottom-left-radius: 0; }
    .bar.cr { border-top-right-radius: 0; border-bottom-right-radius: 0; }
    .bar.dim { opacity: 0.13; }
    .empty-row { font-size: 11px; color: #ccc; line-height: 34px; padding-left: 10px; }
    /* 행사 카드 모달 */
    .ev-modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.55); z-index: 1000; justify-content: center; align-items: flex-start; padding: 40px 16px; overflow-y: auto; }
    .ev-modal.open { display: flex; }
    .ev-card { background: white; border-radius: 16px; max-width: 620px; width: 100%; box-shadow: 0 12px 40px rgba(0,0,0,0.25); overflow: hidden; }
    .ev-head { padding: 16px 20px; border-bottom: 1px solid #f0f0f0; display: flex; align-items: center; gap: 10px; }
    .ev-logo { font-size: 12px; font-weight: 800; padding: 5px 10px; border-radius: 8px; color: white; white-space: nowrap; }
    .ev-name { font-size: 17px; font-weight: 800; flex: 1; color: #1a1a2e; }
    .ev-period { font-size: 12px; color: #fff; background: #ff6b35; padding: 3px 11px; border-radius: 20px; white-space: nowrap; }
    .ev-close { background: none; border: none; font-size: 24px; color: #999; cursor: pointer; line-height: 1; padding: 0 2px; }
    .ev-body { display: flex; gap: 0; }
    .ev-shot { width: 340px; min-width: 340px; border-right: 1px solid #f0f0f0; background: #fafafa; padding: 12px; max-height: 72vh; overflow-y: auto; }
    .ev-shot img { width: 100%; border-radius: 8px; border: 1px solid #eee; display: block; cursor: zoom-in; }
    .ev-shot .cap { font-size: 11px; color: #999; text-align: center; margin-bottom: 8px; }
    .ev-benefits { width: 220px; min-width: 180px; padding: 16px 18px; display: flex; flex-direction: column; gap: 9px; }
    /* 캡처본 크게 보기 */
    .img-zoom { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 1100; justify-content: center; align-items: flex-start; padding: 24px; overflow-y: auto; cursor: zoom-out; }
    .img-zoom.open { display: flex; }
    .img-zoom img { max-width: 440px; width: 100%; height: auto; border-radius: 8px; margin: auto; }
    .img-zoom .zoom-close { position: fixed; top: 14px; right: 20px; color: white; font-size: 34px; cursor: pointer; z-index: 1101; }
    .ev-bf { font-size: 13px; line-height: 1.5; color: #444; }
    .ev-bf .bt { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px; margin-right: 7px; }
    @media (max-width: 760px) { .sched-wrap { padding: 10px; } .ch-label { width: 64px; min-width: 64px; font-size: 11px; }
      .ev-body { flex-direction: column; } .ev-shot { width: 100%; min-width: 0; border-right: none; border-bottom: 1px solid #f0f0f0; max-height: 360px; } .ev-benefits { width: 100%; min-width: 0; } }
  </style>
</head>
<body>
<header>
  <div>
    <h1>홈쇼핑 프로모션 편성표</h1>
    <div class="header-sub">PROMOTION CALENDAR</div>
  </div>
  <nav class="top-nav">
    <a href="index.html">행사 요약</a>
    <a href="schedule.html" class="active">편성표</a>
  </nav>
  <div class="header-right">자동수집</div>
</header>
<div class="header-bar"></div>
<div class="sched-wrap">
  <div class="filters" id="filters">
    <span class="flabel">혜택 필터</span>
  </div>
  <div class="week-nav">
    <button onclick="navWeek(-1)">◀ 지난주</button>
    <span id="week-label" onclick="toggleCal(event)"></span>
    <button onclick="navWeek(1)">다음주 ▶</button>
    <button onclick="goToday()">오늘</button>
    <div class="cal-pop" id="cal-pop"></div>
  </div>
  <div class="gantt" id="grid"></div>
</div>
<div class="ev-modal" id="ev-modal" onclick="if(event.target===this)closeCard()">
  <div class="ev-card" id="ev-card"></div>
</div>
<div class="img-zoom" id="img-zoom" onclick="closeZoom()">
  <span class="zoom-close" onclick="closeZoom()">&times;</span>
  <img id="img-zoom-img" src="" alt="캡처본 크게보기">
</div>
<script>
  const summaries = __SUMMARIES__;
  const TODAY = "__TODAY__";
  const DAY = 86400000;
  const channels = [
    {key:'gs',      label:'GS SHOP',   color:'#3b82c4', soft:'#e8f1fb'},
    {key:'cj',      label:'CJ온스타일', color:'#9b6fc0', soft:'#f3ecfb'},
    {key:'lotte',   label:'롯데홈쇼핑', color:'#d05a5a', soft:'#fbeaea'},
    {key:'hyundai', label:'현대홈쇼핑', color:'#e08a4a', soft:'#fcefe2'},
  ];
  const DOW = ['일','월','화','수','목','금','토'];
  const TYPES = ['카드','적립','쿠폰','할인','특가','경품','사은품'];
  const TYPE_COLORS = {'카드':'#1d4ed8','적립':'#059669','쿠폰':'#db2777','할인':'#c2410c','특가':'#854d0e','경품':'#6d28d9','사은품':'#15803d'};
  const toStr = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const parse = s => { const [y,m,d]=s.split('-').map(Number); return new Date(y,m-1,d); };
  function mondayOf(s){ const d=(typeof s==='string')?parse(s):new Date(s); const dow=(d.getDay()+6)%7; d.setDate(d.getDate()-dow); d.setHours(0,0,0,0); return d; }

  // 기간(period) 텍스트에서 종료일 추출
  function periodEnd(period, startISO){
    if(!period) return null;
    const mds = period.match(/\d{1,2}\/\d{1,2}/g);
    if(!mds) return null;
    const [mo,da] = mds[mds.length-1].split('/').map(Number);
    const sd = parse(startISO);
    let end = new Date(sd.getFullYear(), mo-1, da);
    if(end < sd) end = new Date(sd.getFullYear()+1, mo-1, da);
    return end;
  }

  // 행사명 정규화 (공백·문장부호 제거, 소문자화) 및 매칭
  function nameKey(n){ return (n||'').replace(/\s+/g,'').replace(/[!~·,\/\-_.()]/g,'').toLowerCase(); }
  function nameMatch(a, b){
    const x = nameKey(a), y = nameKey(b);
    if(!x || !y) return false;
    if(x === y) return true;                       // 표기만 다른 동일명
    const [s, l] = x.length <= y.length ? [x, y] : [y, x];
    if(s.length >= 4 && l.includes(s)) return true;  // 한쪽이 다른 쪽을 포함(4자 이상)
    // 접두+접미는 같고 가운데 한두 글자만 삽입된 경우 동일 취급
    // (예: "상반기어워즈" ⟷ "상반기앱어워즈")
    if(s.length >= 4 && l.length - s.length <= 2){
      let p = 0; while(p < s.length && s[p] === l[p]) p++;
      let q = 0; while(q < s.length - p && s[s.length-1-q] === l[l.length-1-q]) q++;
      if(p + q >= s.length) return true;
    }
    return false;
  }

  // summaries → 채널별 이벤트 목록 (간트 막대 단위)
  const events = {gs:[], cj:[], lotte:[], hyundai:[]};
  (function buildEvents(){
    const dates = Object.keys(summaries).sort();
    const byCh = {gs:{}, cj:{}, lotte:{}, hyundai:{}};
    dates.forEach(date => {
      const day = summaries[date] || {};
      channels.forEach(ch => {
        const s = day[ch.key];
        if(!s || !s.name || s.name === '해당없음') return;
        const key = (s.start||date) + '|' + s.name;
        let ev = byCh[ch.key][key];
        if(!ev){ ev = {name:s.name, startISO:s.start||date, period:s.period||'', minD:date, maxD:date, types:new Set()}; byCh[ch.key][key]=ev; }
        if(date < ev.minD) ev.minD = date;
        if(date > ev.maxD) ev.maxD = date;
        if(s.period) ev.period = s.period;
        (s.body||'').split('\n').forEach(l => { l=l.trim(); const i=l.indexOf(':'); if(i>0){ const t=l.slice(0,i).trim(); if(TYPES.includes(t)) ev.types.add(t); } });
      });
    });
    channels.forEach(ch => {
      const occ = Object.values(byCh[ch.key]).map(ev => {
        const start = parse(ev.startISO);
        const pe = periodEnd(ev.period, ev.startISO);
        const maxd = parse(ev.maxD);
        let end = maxd;
        if(pe && pe > end) end = pe;   // 기간 종료일이 더 늦으면 사용
        if(end < start) end = start;
        ev._start = start; ev._end = end;
        return ev;
      });
      // 이름이 같은(표기 흔들림 포함) + 기간이 겹치거나 맞닿는 행사를 하나의 막대로 병합.
      // (패션 클리어런스처럼 start가 갈라진 동일 캠페인, "상반기 어워즈"="상반기어워즈"(공백),
      //  "건강한데이"⊂"건강식품 건강한데이"(포함) 등 통합. 멀리 떨어진 반복 행사는 분리 유지)
      occ.sort((a,b) => a._start - b._start);
      const merged = [];
      occ.forEach(ev => {
        let target = null;
        for(const c of merged){
          const overlap = ev._start.getTime() <= c._end.getTime() + DAY &&
                          ev._end.getTime()   >= c._start.getTime() - DAY;
          if(overlap && nameMatch(c.name, ev.name)){ target = c; break; }
        }
        if(target){
          if(ev._end > target._end) target._end = ev._end;
          if(ev._start < target._start) target._start = ev._start;
          if(ev.minD < target.firstDate) target.firstDate = ev.minD;  // 가장 이른 등장일
          ev.types.forEach(t => target.types.add(t));
          if(ev.period && !target.period) target.period = ev.period;
          // 더 짧고 깔끔한 이름을 대표명으로
          if(nameKey(ev.name).length < nameKey(target.name).length) target.name = ev.name;
        } else {
          merged.push({name:ev.name, period:ev.period, types:new Set(ev.types), _start:ev._start, _end:ev._end, ch:ch.key, firstDate:ev.minD});
        }
      });
      events[ch.key] = merged;
    });
  })();

  // 필터
  let _filter = new Set();
  function buildFilters(){
    const box = document.getElementById('filters');
    const mk = (t, lbl) => `<button class="fchip${t==='ALL'&&_filter.size===0?' active':''}" data-t="${t}" onclick="toggleFilter('${t}')">${lbl}</button>`;
    box.insertAdjacentHTML('beforeend', mk('ALL','전체') + TYPES.map(t=>mk(t,t)).join(''));
  }
  function toggleFilter(t){
    if(t==='ALL') _filter.clear();
    else { _filter.has(t) ? _filter.delete(t) : _filter.add(t); }
    document.querySelectorAll('.fchip').forEach(c => {
      const ct=c.dataset.t;
      c.classList.toggle('active', ct==='ALL' ? _filter.size===0 : _filter.has(ct));
    });
    render();
  }
  function dimmed(ev){
    if(_filter.size===0) return false;
    for(const t of _filter) if(ev.types.has(t)) return false;
    return true;
  }

  // 주간 캘린더 팝업
  let _weekMon, _calMonth;
  function toggleCal(e){
    if(e) e.stopPropagation();
    const p = document.getElementById('cal-pop');
    if(p.classList.contains('open')){ p.classList.remove('open'); return; }
    _calMonth = toStr(_weekMon).slice(0,7);
    renderCal();
    p.classList.add('open');
  }
  function navCalMonth(dir, e){
    if(e) e.stopPropagation();
    const [y,m] = _calMonth.split('-').map(Number);
    const nd = new Date(y, m-1+dir, 1);
    _calMonth = `${nd.getFullYear()}-${String(nd.getMonth()+1).padStart(2,'0')}`;
    renderCal();
  }
  function selectWeek(iso){
    _weekMon = mondayOf(iso);
    document.getElementById('cal-pop').classList.remove('open');
    render();
  }
  function renderCal(){
    const [year,month] = _calMonth.split('-').map(Number);
    const dim = new Date(year, month, 0).getDate();
    const firstDow = (new Date(year, month-1, 1).getDay()+6)%7;
    const weekStart = toStr(_weekMon);
    const weekEnd = toStr(new Date(_weekMon.getTime()+6*DAY));
    let h = `<div class="cal-head"><button onclick="navCalMonth(-1,event)">◀</button><span>${year}년 ${month}월</span><button onclick="navCalMonth(1,event)">▶</button></div>`;
    h += '<table class="cal-table"><tr>' + ['월','화','수','목','금','토','일'].map(d=>`<th>${d}</th>`).join('') + '</tr><tr>';
    let col = 0;
    for(let i=0;i<firstDow;i++){ h+='<td></td>'; col++; }
    for(let day=1; day<=dim; day++){
      const iso = `${_calMonth}-${String(day).padStart(2,'0')}`;
      const has = !!summaries[iso];
      const inweek = iso>=weekStart && iso<=weekEnd;
      const today = iso===TODAY;
      const cls = [has?'has':'no', inweek?'inweek':'', today?'today':''].filter(Boolean).join(' ');
      h += `<td class="${cls}" onclick="selectWeek('${iso}')">${day}</td>`;
      col++;
      if(col%7===0 && day<dim) h+='</tr><tr>';
    }
    h += '</tr></table>';
    document.getElementById('cal-pop').innerHTML = h;
  }
  document.addEventListener('click', e => {
    if(!e.target.closest('#cal-pop') && !e.target.closest('#week-label'))
      document.getElementById('cal-pop')?.classList.remove('open');
  });

  function navWeek(dir){ _weekMon.setDate(_weekMon.getDate()+dir*7); render(); }
  function goToday(){ _weekMon = mondayOf(TODAY); render(); }

  // 막대 클릭 → 해당 행사 첫날 카드(스크린샷+혜택) 모달
  function openCard(ch, date){
    const s = (summaries[date] || {})[ch] || {};
    const meta = channels.find(c => c.key === ch) || {label:ch, color:'#666'};
    let benefits = '';
    (s.body||'').split('\n').forEach(line => {
      line = line.trim();
      if(!line || line === '혜택:') return;
      const i = line.indexOf(':');
      if(i < 0) return;
      const t = line.slice(0,i).trim(), d = line.slice(i+1).trim();
      const c = TYPE_COLORS[t] || '#666';
      benefits += `<div class="ev-bf"><span class="bt" style="background:${c}22;color:${c}">${t}</span>${d}</div>`;
    });
    if(!benefits) benefits = '<div class="ev-bf" style="color:#aaa">표시할 혜택 정보가 없습니다.</div>';
    const shot = `captures/${date}/${ch}_next_tab_full.png`;
    document.getElementById('ev-card').innerHTML =
      `<div class="ev-head">
         <span class="ev-logo" style="background:${meta.color}">${meta.label}</span>
         <span class="ev-name">${s.name||''}</span>
         ${s.period?`<span class="ev-period">${s.period}</span>`:''}
         <button class="ev-close" onclick="closeCard()">&times;</button>
       </div>
       <div class="ev-body">
         <div class="ev-shot"><div class="cap">모바일 캡처본 (${date}) · 클릭 시 크게</div><img src="${shot}" alt="캡처본" onclick="openZoom('${shot}')" onerror="this.parentNode.innerHTML='<div class=cap>캡처 이미지 없음</div>'"></div>
         <div class="ev-benefits">${benefits}</div>
       </div>`;
    document.getElementById('ev-modal').classList.add('open');
  }
  function closeCard(){ document.getElementById('ev-modal').classList.remove('open'); }
  function openZoom(src){
    document.getElementById('img-zoom-img').src = src;
    document.getElementById('img-zoom').classList.add('open');
  }
  function closeZoom(){ document.getElementById('img-zoom').classList.remove('open'); }
  document.addEventListener('keydown', e => {
    if(e.key !== 'Escape') return;
    if(document.getElementById('img-zoom').classList.contains('open')) closeZoom();
    else closeCard();
  });

  function render(){
    const days = [...Array(7)].map((_,i)=>{ const d=new Date(_weekMon); d.setDate(d.getDate()+i); return d; });
    const wStart = new Date(_weekMon);
    const wEnd = new Date(_weekMon.getTime()+6*DAY);
    document.getElementById('week-label').textContent =
      `${wStart.getMonth()+1}/${wStart.getDate()} ~ ${wEnd.getMonth()+1}/${wEnd.getDate()}`;

    // 헤더
    let head = '<div class="g-row g-head"><div class="ch-label head"></div><div class="track">';
    days.forEach(d => {
      const today = toStr(d)===TODAY;
      head += `<div class="dcol${today?' today':''}"><div class="d-date">${d.getMonth()+1}/${d.getDate()}</div><div class="d-dow">${DOW[d.getDay()]}</div></div>`;
    });
    head += '</div></div>';

    let rows = '';
    channels.forEach(ch => {
      const evs = events[ch.key].filter(ev => ev._end>=wStart && ev._start<=wEnd).sort((a,b)=>a._start-b._start);
      // 레인 배치 (겹침 방지)
      const lanes = [];
      evs.forEach(ev => {
        let placed = false;
        for(let li=0; li<lanes.length; li++){
          if(lanes[li] < ev._start){ ev._lane=li; lanes[li]=ev._end; placed=true; break; }
        }
        if(!placed){ ev._lane=lanes.length; lanes.push(ev._end); }
      });
      const laneCount = Math.max(1, lanes.length);
      const rowH = laneCount*30 + 8;
      let lines = '';
      days.forEach((d,i) => { lines += `<div class="gline${toStr(d)===TODAY?' today':''}" style="left:${i/7*100}%"></div>`; });
      let bars = '';
      evs.forEach(ev => {
        const cs = ev._start<wStart ? wStart : ev._start;
        const ce = ev._end>wEnd ? wEnd : ev._end;
        const offset = Math.round((cs-wStart)/DAY);
        const span = Math.round((ce-cs)/DAY)+1;
        const left = offset/7*100, width = span/7*100;
        const contL = ev._start<wStart, contR = ev._end>wEnd;
        const top = ev._lane*30 + 3;
        const tip = `${ev.name}${ev.period?' | '+ev.period:''}${ev.types.size?' | '+[...ev.types].join(', '):''} (클릭 시 첫날 카드)`;
        bars += `<div class="bar${dimmed(ev)?' dim':''}${contL?' cl':''}${contR?' cr':''}" style="left:${left}%;width:${width}%;top:${top}px;background:${ch.soft};color:${ch.color};border:1px solid ${ch.color}33;cursor:pointer" title="${tip}" onclick="openCard('${ev.ch}','${ev.firstDate}')">${ev.name}</div>`;
      });
      if(evs.length===0) bars = '<div class="empty-row">—</div>';
      rows += `<div class="g-row"><div class="ch-label" style="background:${ch.soft};color:${ch.color}">${ch.label}</div><div class="track" style="height:${rowH}px">${lines}${bars}</div></div>`;
    });
    document.getElementById('grid').innerHTML = head + rows;
  }

  buildFilters();
  (function init(){
    const dates = Object.keys(summaries).sort();
    _weekMon = mondayOf(dates.length ? dates[dates.length-1] : TODAY);
    render();
  })();
</script>
</body>
</html>
'''


def build_schedule_html(all_summaries):
    """기존 프로모션 요약 데이터를 주간 그리드(채널×날짜) 편성표로 렌더링."""
    html = (SCHEDULE_TEMPLATE
            .replace('__SUMMARIES__', json.dumps(all_summaries, ensure_ascii=False))
            .replace('__TODAY__', TODAY_KEY))
    with open(os.path.join(BASE_DIR, 'schedule.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print('편성표(schedule.html) 생성 완료')


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

    months_map = {}
    for d in archive_dates:
        ym = d[:7]
        if ym not in months_map:
            months_map[ym] = []
        months_map[ym].append(d)
    latest_month = latest[:7]

    month_btns = '\n'.join(
        f'<button class="month-btn{" active" if ym == latest_month else ""}" data-ym="{ym}" onclick="switchMonth(\'{ym}\')">{ym.replace("-", ".")}</button>'
        for ym in sorted(months_map.keys(), reverse=True)
    )
    day_btns = '\n'.join(
        f'<button class="day-btn{" active" if d == latest else ""}" data-date="{d}" onclick="switchDate(\'{d}\')">{int(d[8:])}일</button>'
        for d in months_map.get(latest_month, [])
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
    header {{ background: white; color: #1a1a2e; padding: 18px 32px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; box-shadow: 0 1px 0 #ebebf0; }}
    header h1 {{ font-size: 20px; font-weight: 800; color: #1a1a2e; letter-spacing: -0.5px; line-height: 1.2; }}
    .header-sub {{ font-size: 10px; color: #bbb; font-weight: 500; letter-spacing: 2px; margin-top: 3px; }}
    .header-right {{ display: flex; align-items: center; gap: 14px; }}
    .top-nav {{ display: flex; gap: 8px; }}
    .top-nav a {{ font-size: 13px; font-weight: 700; color: #888; text-decoration: none; padding: 7px 16px; border-radius: 20px; transition: all 0.15s; }}
    .top-nav a:hover {{ background: #f0f4ff; color: #1a1a2e; }}
    .top-nav a.active {{ background: #1a1a2e; color: white; }}
    .header-date {{ font-size: 13px; color: #666; }}
    .live-dot {{ display: flex; align-items: center; gap: 5px; font-size: 11px; color: #888; }}
    .live-dot::before {{ content: ''; width: 7px; height: 7px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 0 2px #bbf7d0; display: block; }}
    .header-bar {{ height: 3px; background: linear-gradient(to right, #1565c0 25%, #7b1fa2 25% 50%, #c62828 50% 75%, #e65100 75%); position: sticky; top: 57px; z-index: 99; }}
    .page-wrap {{ display: flex; align-items: flex-start; }}
    .sidebar {{ width: 108px; min-width: 108px; position: sticky; top: 20px; margin: 20px 0 20px 20px; display: flex; flex-direction: column; gap: 10px; }}
    .sidebar a {{ display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 12px 8px; border-radius: 14px; text-decoration: none; font-size: 11px; font-weight: 700; color: white; transition: opacity 0.15s, transform 0.15s; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
    .sidebar a:hover {{ opacity: 0.85; transform: translateY(-2px); }}
    .sidebar a .site-icon {{ font-size: 22px; }}
    .sidebar a.gs {{ background: #1565c0; }}
    .sidebar a.cj {{ background: #7b1fa2; }}
    .sidebar a.lotte {{ background: #c62828; }}
    .sidebar a.hyundai {{ background: #e65100; }}
    .main-area {{ flex: 1; min-width: 0; }}
    .date-nav {{ margin: 16px 20px 0; display: flex; align-items: center; position: relative; }}
    .nav-arrow {{ background: white; border: 1px solid #e0e4ff; color: #555; font-size: 11px; padding: 6px 13px; cursor: pointer; transition: all 0.15s; line-height: 1; }}
    .nav-arrow:hover {{ background: #f0f4ff; }}
    .nav-arrow:disabled {{ opacity: 0.3; cursor: default; }}
    .nav-arrow:first-child {{ border-radius: 8px 0 0 8px; border-right: none; }}
    .nav-arrow:last-child  {{ border-radius: 0 8px 8px 0; border-left: none; }}
    .nav-date {{ background: white; border: 1px solid #e0e4ff; color: #1a1a2e; font-size: 14px; font-weight: 700; padding: 6px 20px; cursor: pointer; transition: background 0.15s; letter-spacing: 0.3px; }}
    .nav-date:hover {{ background: #f0f4ff; }}
    .cal-pop {{ display: none; position: absolute; top: 38px; left: 0; z-index: 200; background: white; border: 1px solid #e0e4ff; border-radius: 12px; padding: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); min-width: 260px; }}
    .cal-pop.open {{ display: block; }}
    .container {{ margin: 20px 20px 32px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }}
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
    .summary {{ flex: 1; padding: 16px 20px; overflow-y: auto; max-height: 600px; display: flex; flex-direction: column; gap: 8px; }}
    .modal {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 1000; justify-content: center; align-items: flex-start; padding: 24px; overflow-y: auto; }}
    .modal.open {{ display: flex; }}
    .modal img {{ max-width: 390px; width: 100%; border-radius: 12px; margin: auto; }}
    .modal-close {{ position: fixed; top: 16px; right: 20px; color: white; font-size: 32px; cursor: pointer; z-index: 1001; }}
  </style>
</head>
<body>
<header>
  <div>
    <h1>홈쇼핑 행사 요약</h1>
    <div class="header-sub">HOMESHOPPING WEEKLY</div>
  </div>
  <nav class="top-nav">
    <a href="index.html" class="active">행사 요약</a>
    <a href="schedule.html">편성표</a>
  </nav>
  <div class="header-right">
    <span class="header-date" id="header-date">기준일: {TODAY_KEY}</span>
    <span class="live-dot">자동수집</span>
  </div>
</header>
<div class="header-bar"></div>
<div class="page-wrap">
<aside class="sidebar">
  <a class="gs" href="https://m.gsshop.com" target="_blank">
    <span class="site-icon">🛒</span>GS SHOP
  </a>
  <a class="cj" href="https://display.cjonstyle.com/m/homeTab/main" target="_blank">
    <span class="site-icon">🛍️</span>CJ온스타일
  </a>
  <a class="lotte" href="https://m.lotteimall.com" target="_blank">
    <span class="site-icon">🏪</span>롯데홈쇼핑
  </a>
  <a class="hyundai" href="https://www.hmall.com" target="_blank">
    <span class="site-icon">🏬</span>현대홈쇼핑
  </a>
</aside>
<div class="main-area">
<div id="trend-banner" style="margin:16px 20px 0;background:#f8f9ff;border:1px solid #e0e4ff;border-radius:10px;padding:10px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;"></div>
<div class="date-nav" id="date-nav">
  <button class="nav-arrow" id="prev-btn" onclick="navDate(-1)">◀</button>
  <button class="nav-date"  id="cur-date-btn" onclick="toggleCal()">{latest}</button>
  <button class="nav-arrow" id="next-btn" onclick="navDate(1)">▶</button>
  <div class="cal-pop" id="cal-pop"></div>
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
</div><!-- main-area -->
</div><!-- page-wrap -->
<div class="modal" id="modal" onclick="closeModal()">
  <span class="modal-close" onclick="closeModal()">✕</span>
  <img id="modal-img" src="" alt="">
</div>
<script>
  const BRAND_COLORS = {{gs:'#1565c0',cj:'#7b1fa2',lotte:'#c62828',hyundai:'#e65100'}};
  const BRANDS_ORDER = ['gs','cj','lotte','hyundai'];
  let _activeDate = '';
  const TAG_COLORS = {{
    '카드':    {{bg:'#dbeafe',color:'#1d4ed8',border:'#93c5fd'}},
    '적립':    {{bg:'#dcfce7',color:'#166534',border:'#86efac'}},
    '쿠폰':    {{bg:'#fce7f3',color:'#9d174d',border:'#f9a8d4'}},
    '할인':    {{bg:'#ffedd5',color:'#c2410c',border:'#fdba74'}},
    '특가':    {{bg:'#fef9c3',color:'#854d0e',border:'#fde047'}},
    '경품':    {{bg:'#f5f3ff',color:'#6d28d9',border:'#c4b5fd'}},
    '무료배송':{{bg:'#e0f2fe',color:'#0369a1',border:'#7dd3fc'}},
    '사은품':  {{bg:'#f0fdf4',color:'#15803d',border:'#86efac'}},
  }};
  function renderSummary(text) {{
    if (!text) return '';
    if (text === NO_BODY) return `<span style="color:#aaa;font-size:12px">${{text}}</span>`;
    const lines = text.split('\\n');
    const rows = [];
    for (const line of lines) {{
      const t = line.trim();
      if (!t || t === '혜택:') continue;
      const m = t.match(/^([가-힣a-zA-Z·]+):\s*(.+)$/);
      if (m) {{
        const c = TAG_COLORS[m[1]] || {{bg:'#f3f4f6',color:'#374151',border:'#d1d5db'}};
        rows.push(`<div style="display:flex;align-items:flex-start;gap:7px">
          <span style="background:${{c.bg}};color:${{c.color}};border:1px solid ${{c.border}};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;white-space:nowrap;flex-shrink:0;margin-top:2px">${{m[1]}}</span>
          <span style="font-size:13px;color:#444;line-height:1.5">${{m[2]}}</span>
        </div>`);
      }} else {{
        rows.push(`<div style="font-size:13px;color:#666">${{t}}</div>`);
      }}
    }}
    return rows.join('') || `<span style="color:#aaa;font-size:12px">${{text}}</span>`;
  }}
  function renderAll() {{
    ['gs','cj','lotte','hyundai'].forEach(b => {{
      const el = g(b+'-summary');
      if (el) el.innerHTML = renderSummary(el.textContent);
    }});
    _activeDate = Object.keys(summaries).sort((a,b) => b.localeCompare(a))[0] || '';
    updateNavBtns();
    renderWeeklyTrend();
  }}
  function renderWeeklyTrend() {{
    const el = g('trend-banner');
    if (!el) return;
    const allDates = Object.keys(summaries).sort((a,b) => b.localeCompare(a));
    const week = allDates.slice(0, 7);
    if (week.length < 2) return;
    const tagCounts = {{}}, tagChannels = {{}};
    const brands = ['gs','cj','lotte','hyundai'];
    const seenEvents = new Set();
    for (const d of week) {{
      const obj = summaries[d] || {{}};
      for (const brand of brands) {{
        const b = obj[brand];
        if (!b || !b.body) continue;
        const eventKey = brand + '|' + (b.start || d);
        if (seenEvents.has(eventKey)) continue;
        seenEvents.add(eventKey);
        for (const line of b.body.split('\\n')) {{
          const m = line.trim().match(/^([가-힣a-zA-Z·]+):\s*.+/);
          if (!m) continue;
          const tag = m[1];
          tagCounts[tag] = (tagCounts[tag] || 0) + 1;
          if (!tagChannels[tag]) tagChannels[tag] = new Set();
          tagChannels[tag].add(brand);
        }}
      }}
    }}
    const sorted = Object.entries(tagCounts).sort((a,b) => b[1]-a[1]);
    if (!sorted.length) return;
    const from = week[week.length-1].slice(5).replace('-','/');
    const to   = week[0].slice(5).replace('-','/');
    const pills = sorted.slice(0, 5).map(([tag, cnt]) => {{
      const c = TAG_COLORS[tag] || {{bg:'#f3f4f6',color:'#374151',border:'#d1d5db'}};
      const ch = tagChannels[tag] ? tagChannels[tag].size : 0;
      const hint = ch === 4 ? ' · 4개사 공통' : ch >= 3 ? ` · ${{ch}}개사` : '';
      return `<span style="background:${{c.bg}};color:${{c.color}};border:1px solid ${{c.border}};padding:3px 10px;border-radius:5px;font-size:11px;font-weight:700;white-space:nowrap">${{tag}} ${{cnt}}건${{hint}}</span>`;
    }}).join('');
    el.innerHTML = `<span style="color:#666;font-size:11px;font-weight:700;white-space:nowrap">📊 ${{from}}~${{to}}</span><div style="display:flex;gap:6px;flex-wrap:wrap">${{pills}}</div>`;
  }}
  function navDate(dir) {{
    const dates = Object.keys(summaries).sort();
    const idx = dates.indexOf(_activeDate);
    const ni = idx + dir;
    if (ni >= 0 && ni < dates.length) switchDate(dates[ni]);
  }}
  function updateNavBtns() {{
    const dates = Object.keys(summaries).sort();
    const idx = dates.indexOf(_activeDate);
    const prev = g('prev-btn'), next = g('next-btn');
    if (prev) prev.disabled = idx <= 0;
    if (next) next.disabled = idx >= dates.length - 1;
    const btn = g('cur-date-btn');
    if (btn) btn.textContent = _activeDate;
  }}
  let _calMonth = '';
  function toggleCal() {{
    const pop = g('cal-pop');
    if (!pop) return;
    if (pop.classList.contains('open')) {{ pop.classList.remove('open'); return; }}
    _calMonth = _activeDate.slice(0, 7);
    renderCalPop(_calMonth);
    pop.classList.add('open');
  }}
  function navCalMonth(dir) {{
    const [y, m] = _calMonth.split('-').map(Number);
    const nd = new Date(y, m - 1 + dir, 1);
    _calMonth = `${{nd.getFullYear()}}-${{String(nd.getMonth()+1).padStart(2,'0')}}`;
    renderCalPop(_calMonth);
  }}
  function renderCalPop(ym) {{
    const [year, month] = ym.split('-').map(Number);
    const dim = new Date(year, month, 0).getDate();
    const firstDow = (new Date(year, month-1, 1).getDay() + 6) % 7;
    const now = new Date();
    const todayStr = `${{now.getFullYear()}}-${{String(now.getMonth()+1).padStart(2,'0')}}-${{String(now.getDate()).padStart(2,'0')}}`;
    const allDates = Object.keys(summaries);
    const hasPrev = allDates.some(d => d < `${{ym}}-01`);
    const hasNext = allDates.some(d => d > `${{ym}}-32`);
    const DOW = ['월','화','수','목','금','토','일'];
    let html = `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <button onclick="event.stopPropagation();navCalMonth(-1)" style="background:none;border:none;cursor:pointer;font-size:13px;padding:2px 8px;opacity:${{hasPrev?1:0.25}};pointer-events:${{hasPrev?'auto':'none'}}">◀</button>
      <span style="font-size:13px;font-weight:700;color:#1a1a2e">${{year}}년 ${{month}}월</span>
      <button onclick="event.stopPropagation();navCalMonth(1)"  style="background:none;border:none;cursor:pointer;font-size:13px;padding:2px 8px;opacity:${{hasNext?1:0.25}};pointer-events:${{hasNext?'auto':'none'}}">▶</button>
    </div>`;
    html += '<table style="width:100%;border-collapse:separate;border-spacing:3px">';
    html += '<tr>' + DOW.map(h => `<th style="text-align:center;font-size:10px;color:#aaa;padding:2px 0;font-weight:600">${{h}}</th>`).join('') + '</tr>';
    let day = 1;
    for (let row = 0; row < 6; row++) {{
      if (day > dim) break;
      html += '<tr>';
      for (let col = 0; col < 7; col++) {{
        if (row === 0 && col < firstDow || day > dim) {{ html += '<td></td>'; }}
        else {{
          const d = `${{ym}}-${{String(day).padStart(2,'0')}}`;
          const isAct = d === _activeDate, isTod = d === todayStr, hasData = !!summaries[d];
          const bg  = isAct ? '#1a1a2e' : (isTod ? '#eef2ff' : 'transparent');
          const clr = isAct ? 'white' : (hasData ? (isTod ? '#1d4ed8' : '#333') : '#ccc');
          const onclick = hasData ? `onclick="switchDate('${{d}}');toggleCal()"` : '';
          html += `<td ${{onclick}} style="${{hasData?'cursor:pointer;':''}}text-align:center;padding:6px 3px;border-radius:7px;background:${{bg}}">
            <span style="font-size:13px;color:${{clr}};font-weight:${{(isAct||isTod)?'700':'400'}}">${{day}}</span>
          </td>`;
          day++;
        }}
      }}
      html += '</tr>';
    }}
    html += '</table>';
    g('cal-pop').innerHTML = html;
  }}
  document.addEventListener('click', e => {{
    if (!e.target.closest('#date-nav')) g('cal-pop')?.classList.remove('open');
  }});
  function renderCalendar(ym) {{
    const [year, month] = ym.split('-').map(Number);
    const daysInMonth = new Date(year, month, 0).getDate();
    const firstDow = (new Date(year, month-1, 1).getDay() + 6) % 7;
    const now = new Date();
    const todayStr = `${{now.getFullYear()}}-${{String(now.getMonth()+1).padStart(2,'0')}}-${{String(now.getDate()).padStart(2,'0')}}`;
    const DOW = ['월','화','수','목','금','토','일'];
    let html = '<table style="width:100%;border-collapse:separate;border-spacing:4px">';
    html += '<tr>' + DOW.map(h => `<th style="text-align:center;font-size:10px;color:#aaa;padding:3px 0;font-weight:600">${{h}}</th>`).join('') + '</tr>';
    let day = 1;
    for (let row = 0; row < 6; row++) {{
      if (day > daysInMonth) break;
      html += '<tr>';
      for (let col = 0; col < 7; col++) {{
        if (row === 0 && col < firstDow || day > daysInMonth) {{
          html += '<td></td>';
        }} else {{
          const d = `${{ym}}-${{String(day).padStart(2,'0')}}`;
          const data = summaries[d];
          const isActive = d === _activeDate, isToday = d === todayStr;
          const bg     = isActive ? '#1a1a2e' : (data ? (isToday ? '#eef2ff' : 'white') : 'transparent');
          const border = isActive ? '1px solid #1a1a2e' : (data ? `1px solid ${{isToday ? '#93c5fd' : '#e8eaf0'}}` : 'none');
          const numColor  = isActive ? 'white' : (data ? (isToday ? '#1d4ed8' : '#333') : '#ddd');
          const numWeight = (isActive || isToday) ? '700' : '400';
          const dots = data ? BRANDS_ORDER
            .filter(b => data[b] && data[b].name && data[b].name !== '해당없음')
            .map(b => `<span style="width:5px;height:5px;border-radius:50%;background:${{BRAND_COLORS[b]}};display:inline-block;flex-shrink:0"></span>`)
            .join('') : '';
          const onclick = data ? ` onclick="switchDate('${{d}}')"` : '';
          html += `<td data-date="${{d}}"${{onclick}} style="${{data?'cursor:pointer;':''}}text-align:center;padding:5px 2px;border-radius:8px;background:${{bg}};border:${{border}}">
            <div class="cal-num" style="font-size:12px;color:${{numColor}};font-weight:${{numWeight}};margin-bottom:3px;line-height:1">${{day}}</div>
            <div style="display:flex;justify-content:center;gap:2px;min-height:6px">${{dots}}</div>
          </td>`;
          day++;
        }}
      }}
      html += '</tr>';
    }}
    html += '</table>';
    g('day-nav').innerHTML = html;
  }}
  document.addEventListener('DOMContentLoaded', renderAll);
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
  function normDate(s) {{
    s = s.trim();
    let m = s.match(/^([0-9]{{4}})[./-]([0-9]{{1,2}})[./-]([0-9]{{1,2}})$/);
    if (m) return parseInt(m[2]) + '/' + m[3].padStart(2,'0');
    m = s.match(/^([0-9]{{1,2}})[./-]([0-9]{{1,2}})$/);
    if (m) return parseInt(m[1]) + '/' + m[2].padStart(2,'0');
    return s;
  }}
  function sfield(obj, brand, field, fb) {{
    const b = obj[brand]; if (!b) return fb;
    if (typeof b !== 'object') return field==='body' ? b : fb;
    if (field === 'period') {{
      const start = b.start || '';
      const period = b.period || '';
      const end = period ? extractEnd(period) : null;
      // AI가 시작일도 알면(period에 ~ 앞이 날짜이면) 그대로 사용
      if (period && period.includes('~')) {{
        const beforeTilde = period.split('~')[0].trim();
        if (/[0-9]{{1,4}}[./-][0-9]{{1,2}}/.test(beforeTilde) && end) {{
          return normDate(beforeTilde) + ' ~ ' + end;
        }}
      }}
      if (start && end) return fmtStart(start) + ' ~ ' + end;
      // 텍스트 기간(매주 화요일 등)이면 그대로
      if (period && !/^[0-9./ -]+$/.test(period.trim())) return period;
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
    // 현대 행사 없음 여부에 따라 카드 스타일 토글
    const hyundaiName = sfield(obj,'hyundai','name','');
    const noEvent = hyundaiName === '해당없음';
    const hyundaiCard = g('hyundai-name').closest('.card');
    if (hyundaiCard) hyundaiCard.classList.toggle('no-event', noEvent);
    // 현대 기간 배지: 행사 없음이면 텍스트/색상 변경
    const periodEl = g('hyundai-period');
    if (periodEl) {{
      if (noEvent) {{
        periodEl.textContent = '행사 없음';
        periodEl.style.background = '#bbb';
      }} else {{
        periodEl.textContent = sfield(obj,'hyundai','period',d);
        periodEl.style.background = '';
      }}
    }}
    g('gs-period').textContent    = sfield(obj,'gs','period',d);
    g('cj-period').textContent    = sfield(obj,'cj','period',d);
    g('lotte-period').textContent = sfield(obj,'lotte','period',d);
    g('hyundai-summary').innerHTML = renderSummary(noEvent ? '' : sfield(obj,'hyundai','body',NO_BODY));
    g('gs-summary').innerHTML      = renderSummary(sfield(obj,'gs','body',NO_BODY));
    g('cj-summary').innerHTML      = renderSummary(sfield(obj,'cj','body',NO_BODY));
    g('lotte-summary').innerHTML   = renderSummary(sfield(obj,'lotte','body',NO_BODY));
    g('header-date').textContent = '기준일: ' + d;
    _activeDate = d;
    updateNavBtns();
  }}
  function switchMonth(ym) {{
    document.querySelectorAll('.month-btn').forEach(b => b.classList.toggle('active', b.dataset.ym === ym));
    renderCalendar(ym);
  }}
</script>
</body>
</html>"""

    with open(os.path.join(BASE_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'HTML 업데이트 완료: {TODAY}')

    build_schedule_html(all_summaries)


def git_push(archive_date_dir):
    """캡처 결과를 GitHub에 자동 push"""
    import subprocess
    rel = os.path.relpath(archive_date_dir, BASE_DIR).replace('\\', '/')
    candidates = [
        'index.html', 'schedule.html', 'promo_history.json',
        f'{rel}/hyundai_next_tab_full.png', f'{rel}/hyundai_banner.png', f'{rel}/hyundai_page_text.txt',
        f'{rel}/gs_next_tab_full.png',      f'{rel}/gs_banner.png',      f'{rel}/gs_page_text.txt',
        f'{rel}/cj_next_tab_full.png',      f'{rel}/cj_banner.png',      f'{rel}/cj_page_text.txt',
        f'{rel}/lotte_next_tab_full.png',   f'{rel}/lotte_banner.png',   f'{rel}/lotte_page_text.txt',
        f'{rel}/summary.json',
        f'{rel}/tab_names.json',
    ]
    files_to_add = [f for f in candidates if os.path.exists(os.path.join(BASE_DIR, f.replace('/', os.sep)))]

    def run_git(args, check=False):
        r = subprocess.run(['git', '-C', BASE_DIR] + args,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        out = (r.stdout + r.stderr).strip()
        if out: print(out)
        return r.returncode

    run_git(['add', '--force'] + files_to_add)

    rc = run_git(['commit', '-m', f'Auto update: {TODAY}'])
    if rc not in (0, 1):  # 1 = nothing to commit
        print(f'git commit 실패 (rc={rc})')
        return

    # push 실패 시 pull --rebase 후 재시도
    rc = run_git(['push', 'origin', 'main'])
    if rc != 0:
        print('push 실패 → pull --rebase 후 재시도')
        run_git(['pull', '--rebase', 'origin', 'main'])
        rc = run_git(['push', 'origin', 'main'])
        if rc != 0:
            print('push 재시도 실패 — 로컬에는 저장됨')


if __name__ == '__main__':
    import sys, subprocess as _sp

    # 로그 파일 출력 (작업 스케줄러는 콘솔이 없어 sys.__stdout__ 사용 불가)
    log_path = os.path.join(BASE_DIR, 'capture_log.txt')
    log_f = open(log_path, 'a', encoding='utf-8')
    class Tee:
        def write(self, msg):
            try:
                sys.__stdout__.write(msg)
                sys.__stdout__.flush()
            except Exception:
                pass  # 콘솔 없는 환경(작업 스케줄러)에서는 무시
            log_f.write(msg)
            log_f.flush()
        def flush(self):
            try: sys.__stdout__.flush()
            except Exception: pass
            log_f.flush()
    sys.stdout = Tee()
    sys.stderr = Tee()  # 에러도 로그에 기록

    import time as _time
    _script_start = _time.time()
    def check_timeout(label='', limit_min=90):
        elapsed = (_time.time() - _script_start) / 60
        if elapsed > limit_min:
            print(f'[경고] 실행 {elapsed:.0f}분 초과 ({limit_min}분 제한) — {label}')
            return True
        return False

    print(f'\n[{TODAY}] 홈쇼핑 자동 캡처 시작...')

    # playwright 브라우저 자동 설치 (업데이트 후 경로 변경 대비) — 로그에 결과 기록
    # NODE_TLS_REJECT_UNAUTHORIZED=0 : 회사 프록시 self-signed 인증서 우회
    print('playwright install 실행 중...')
    import copy
    pw_env = copy.copy(os.environ)
    pw_env['NODE_TLS_REJECT_UNAUTHORIZED'] = '0'
    pw_result = _sp.run(
        [sys.executable, '-m', 'playwright', 'install', 'chromium'],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        env=pw_env
    )
    if pw_result.returncode != 0:
        print(f'playwright install 실패 (rc={pw_result.returncode}): {pw_result.stderr[:200]}')
    else:
        print('playwright install 완료')

    archive_date_dir = os.path.join(ARCHIVE_DIR, TODAY_KEY)
    os.makedirs(archive_date_dir, exist_ok=True)

    hyundai_tab = gs_tab = cj_tab = lotte_tab = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for name, func in [('현대', run_hyundai), ('GS', run_gs), ('CJ', run_cj), ('롯데', run_lotte)]:
                try:
                    tab = _run_with_retry(func, browser, archive_date_dir, retries=2)
                    print(f'{name} 완료: {tab}')
                    if name == '현대': hyundai_tab = tab
                    elif name == 'GS': gs_tab = tab
                    elif name == 'CJ': cj_tab = tab
                    elif name == '롯데': lotte_tab = tab
                except Exception as e:
                    print(f'{name} 캡처 최종 실패: {e}')
            browser.close()
    except Exception as e:
        print(f'브라우저 실행 실패: {e}')

    print('AI 요약 생성 중...')
    try:
        generate_summary(archive_date_dir, hyundai_tab, gs_tab, cj_tab, lotte_tab)
    except Exception as e:
        print(f'요약 실패: {e}')

    print('진행 중 행사 요약 통합 중...')
    try:
        consolidate_ongoing_events()
    except Exception as e:
        print(f'consolidate 실패: {e}')

    print('기간(period) 날짜 오독 검증 중...')
    try:
        validate_periods()
    except Exception as e:
        print(f'기간검증 실패: {e}')

    try:
        archive_dates = get_archive_dates()
        update_html(hyundai_tab, gs_tab, cj_tab, lotte_tab, archive_dates)
    except Exception as e:
        print(f'HTML 업데이트 실패: {e}')

    try:
        git_push(archive_date_dir)
    except Exception as e:
        print(f'git push 실패: {e}')

    print('전체 완료! GitHub Pages 자동 업데이트됨')
    log_f.close()
