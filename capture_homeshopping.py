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


def capture_full(page, path):
    page.screenshot(path=path, full_page=True, timeout=60000, animations='disabled')
    return path


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
        (skipLabels) => {
            const tabs = Array.from(document.querySelectorAll('[class*=main] nav a, .sc-dp-display nav a'));
            const idx = tabs.findIndex(a => a.innerText.trim() === '현대홈쇼핑');
            if (idx < 0) return null;
            let nextIdx = idx + 1;
            if (nextIdx < tabs.length && skipLabels.length > 0) {
                const nextText = tabs[nextIdx].innerText.trim();
                const shouldSkip = skipLabels.some(s => nextText.includes(s));
                if (shouldSkip && nextIdx + 1 < tabs.length) nextIdx++;
            }
            if (nextIdx < tabs.length) {
                tabs[nextIdx].click();
                return tabs[nextIdx].innerText.trim();
            }
            return null;
        }
    """, HYUNDAI_SKIP_TABS)
    # 현대 탭 목록 별도 저장 (현대홈쇼핑 기준 이후 탭, 최대 15개·중복 제거)
    hyundai_tabs = page.evaluate("""
        () => {
            const tabs = Array.from(document.querySelectorAll('[class*=main] nav a, .sc-dp-display nav a'));
            const idx = tabs.findIndex(a => a.innerText.trim() === '현대홈쇼핑');
            if (idx < 0) return [];
            const seen = new Set();
            const result = [];
            for (const a of tabs.slice(idx)) {
                const t = a.innerText.split('\\n')[0].trim();
                if (!t) continue;
                if (seen.has(t)) break;
                seen.add(t);
                result.push(t);
                if (result.length >= 15) break;
            }
            return result;
        }
    """)
    save_tab_names(archive_dir, 'hyundai', hyundai_tabs or [])
    page.wait_for_timeout(2000)
    close_popups(page)
    capture_full(page, os.path.join(archive_dir, 'hyundai_next_tab_full.png'))
    capture_banner(page, os.path.join(archive_dir, 'hyundai_banner.png'))
    save_page_text(page, os.path.join(archive_dir, 'hyundai_page_text.txt'))
    page.close()
    return tab_name


def _run_with_retry(func, browser, archive_dir, retries=2):
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
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://m.gsshop.com', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(3000)
    close_popups_gs(page)
    page.wait_for_timeout(1000)
    close_popups_gs(page)
    save_tab_names(archive_dir, 'gs', get_all_tabs(page))
    tab_name = click_next_tab(page)
    page.wait_for_timeout(3000)
    try:
        page.wait_for_load_state('networkidle', timeout=8000)
    except: pass
    close_popups_gs(page)
    capture_full(page, os.path.join(archive_dir, 'gs_next_tab_full.png'))
    capture_banner(page, os.path.join(archive_dir, 'gs_banner.png'))
    save_page_text(page, os.path.join(archive_dir, 'gs_page_text.txt'))
    page.close()
    return tab_name


CJ_SKIP_TABS = ['라이브쇼특가', '매일특가']        # CJ: 홈 바로 옆이 이 탭이면 그 다음 탭으로 이동
HYUNDAI_SKIP_TABS = ['오감쇼']                    # 현대: 방송 프로그램 탭 스킵 → 피드백 시 추가

def run_cj(browser, archive_dir):
    """CJ온스타일 캡처"""
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(3000)
    close_popups(page)
    save_tab_names(archive_dir, 'cj', get_all_tabs(page))
    tab_name = click_next_tab(page, skip_labels=CJ_SKIP_TABS)
    page.wait_for_timeout(2000)
    close_popups(page)
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
    page = browser.new_page(viewport=VIEWPORT, user_agent=MOBILE_UA)
    page.goto('https://m.lotteimall.com', wait_until='domcontentloaded', timeout=60000)
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
    '프로모션 행사가 아닌 브랜드관으로 판단하여 "해당없음"으로 처리하세요. '
    '카드 할인, 적립, 쿠폰 등 구체적인 혜택이 하나도 없는 단순 방송 홍보(예: 오감쇼, 스페셜방송 등)도 '
    '"해당없음"으로 처리하세요. 혜택 항목을 작성할 수 없으면 반드시 "해당없음"입니다.'
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
    .date-nav {{ margin: 20px 20px 0; display: flex; gap: 8px; flex-wrap: wrap; }}
    .date-btn {{ padding: 6px 14px; border-radius: 20px; border: 1px solid #ddd; background: white; font-size: 13px; cursor: pointer; color: #555; }}
    .date-btn.active {{ background: #1a1a2e; color: white; border-color: #1a1a2e; font-weight: 700; }}
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
</div><!-- main-area -->
</div><!-- page-wrap -->
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
    g('hyundai-summary').textContent = noEvent ? '' : sfield(obj,'hyundai','body',NO_BODY);
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
