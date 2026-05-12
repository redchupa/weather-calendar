import os
import math
import requests
import pytz
from datetime import datetime, timedelta, date
from icalendar import Calendar, Event
from astral import LocationInfo, moon
from astral.sun import sun, dawn as astral_dawn, dusk as astral_dusk
import ephem

# --- [1. 설정] ---
NX = int(os.environ.get('KMA_NX', 60))
NY = int(os.environ.get('KMA_NY', 127))
LOCATION_NAME = os.environ.get('LOCATION_NAME', '내 위치')
REG_ID_TEMP = os.environ.get('REG_ID_TEMP', '11B10101')
REG_ID_LAND = os.environ.get('REG_ID_LAND', '11B00000')
API_KEY = os.environ['KMA_API_KEY']

# 기상특보 옵션:
# - WRN_KEYWORDS: 쉼표로 구분된 지역 키워드 (예: "서울,경기,수도권"). 비어 있으면 전국 경보만 표시
# - WRN_INCLUDE_WATCH: '1'이면 주의보까지 모두 표시. 기본값 '0' (경보만)
WRN_KEYWORDS = [k.strip() for k in os.environ.get('WRN_KEYWORDS', '').split(',') if k.strip()]
WRN_INCLUDE_WATCH = os.environ.get('WRN_INCLUDE_WATCH', '0') == '1'

# 특보 종류 → (이모지, 한글명)
WRN_INFO = {
    'W': ('💨', '강풍'),
    'R': ('🌧️', '호우'),
    'C': ('🥶', '한파'),
    'D': ('🔥', '건조'),
    'O': ('🌊', '폭풍해일'),
    'N': ('🌊', '지진해일'),
    'V': ('🌊', '풍랑'),
    'T': ('🌀', '태풍'),
    'S': ('❄️', '대설'),
    'Y': ('💛', '황사'),
    'H': ('🥵', '폭염'),
    'F': ('🌫️', '안개'),
}

# 미세먼지/초미세먼지 옵션 (에어코리아 via 공공데이터포털)
# - DATA_GO_KR_KEY: 공공데이터포털 일반 인증키
# - DATA_GO_KR_REGION: 에어코리아 예보 지역명 (예: '서울', '경기북부', '경기남부', '강원영서')
# 두 값 모두 설정해야 미세먼지 기능 활성화. 하나라도 비어 있으면 기능 비활성 (워크플로우는 정상 동작).
DATA_GO_KR_KEY = os.environ.get('DATA_GO_KR_KEY', '').strip()
DATA_GO_KR_REGION = os.environ.get('DATA_GO_KR_REGION', '').strip()

# 생활/보건기상지수용 행정표준코드 (10자리, 시군구 단위)
# - 정확한 시군구 코드를 LIVING_AREA_NO 시크릿으로 등록하는 게 가장 좋음
# - 없으면 DATA_GO_KR_REGION 기반 광역 fallback 사용 (정확도 낮음)
LIVING_AREA_DEFAULTS = {
    '서울': '1100000000', '부산': '2600000000', '대구': '2700000000',
    '인천': '2800000000', '광주': '2900000000', '대전': '3000000000',
    '울산': '3100000000', '세종': '3611000000',
    '경기북부': '4100000000', '경기남부': '4100000000',
    '강원영서': '4200000000', '강원영동': '4200000000',
    '충북': '4300000000', '충남': '4400000000',
    '전북': '5200000000', '전남': '4600000000',
    '경북': '4700000000', '경남': '4800000000', '제주': '5000000000',
}
LIVING_AREA_NO = os.environ.get('LIVING_AREA_NO', '').strip() or LIVING_AREA_DEFAULTS.get(DATA_GO_KR_REGION, '')

PM_GRADE_EMOJI = {
    '좋음': '🟢',
    '보통': '🟡',
    '나쁨': '🟠',
    '매우나쁨': '🔴',
}

def get_weather_info(sky, pty):
    sky, pty = str(sky), str(pty)
    if pty == '1': return "🌧️", "비"
    if pty == '2': return "🌨️", "비/눈(진눈깨비)"
    if pty == '3': return "❄️", "눈"
    if pty == '4': return "☔", "소나기"
    if pty == '5': return "💧", "빗방울"
    if pty == '6': return "🌨️", "빗방울/눈날림"
    if pty == '7': return "❄️", "눈날림"
    if sky == '1': return "☀️", "맑음"
    if sky == '3': return "⛅", "구름많음"
    if sky == '4': return "☁️", "흐림"
    return "🌡️", "정보없음"

def get_mid_emoji(wf):
    if not wf: return "🌡️"
    wf = wf.replace(" ", "")
    if '소나기' in wf: return "☔"
    if '비' in wf: return "🌧️"
    if '눈' in wf or '진눈깨비' in wf: return "🌨️"
    if '구름많음' in wf: return "⛅"
    if '흐림' in wf: return "☁️"
    if '맑음' in wf: return "☀️"
    return "☀️"

def fetch_api(url, label=""):
    try:
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            print(f"[WARN] {label or 'API'} HTTP {res.status_code}: {res.text[:200]}")
            return None
        data = res.json()
        result_code = data.get('response', {}).get('header', {}).get('resultCode')
        if result_code != '00':
            msg = data.get('response', {}).get('header', {}).get('resultMsg', 'unknown')
            print(f"[WARN] {label or 'API'} resultCode={result_code} ({msg})")
            return None
        return data
    except requests.exceptions.Timeout:
        print(f"[WARN] {label or 'API'} timeout (15s)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[WARN] {label or 'API'} request failed: {e}")
        return None
    except ValueError as e:
        print(f"[WARN] {label or 'API'} JSON parse failed: {e}")
        return None

def get_base_datetime(now):
    release_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    effective_now = now - timedelta(minutes=10)
    valid = [h for h in release_hours if h <= effective_now.hour]
    if valid:
        base_h = max(valid)
        return effective_now.strftime('%Y%m%d'), f"{base_h:02d}00"
    else:
        prev = effective_now - timedelta(days=1)
        return prev.strftime('%Y%m%d'), "2300"

def get_tmfc_candidates(now):
    candidates = []
    effective_now = now - timedelta(minutes=30)
    if effective_now.hour < 6:
        c1 = (effective_now - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        c2 = (effective_now - timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
    elif effective_now.hour < 18:
        c1 = effective_now.replace(hour=6, minute=0, second=0, microsecond=0)
        c2 = (effective_now - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    else:
        c1 = effective_now.replace(hour=18, minute=0, second=0, microsecond=0)
        c2 = effective_now.replace(hour=6, minute=0, second=0, microsecond=0)
    candidates.append(c1)
    candidates.append(c2)
    return candidates

def load_cached_events(ics_path):
    """기존 weather.ics에서 날짜별 이벤트를 raw 바이트로 캐싱"""
    cache = {}
    if not os.path.exists(ics_path):
        return cache
    try:
        with open(ics_path, 'rb') as f:
            cal = Calendar.from_ical(f.read())
        for component in cal.walk():
            if component.name == 'VEVENT':
                dtstart = component.get('dtstart')
                if dtstart:
                    d = dtstart.dt
                    if hasattr(d, 'strftime'):
                        d_str = d.strftime('%Y%m%d')
                        cache[d_str] = component.to_ical()
    except (IOError, ValueError) as e:
        print(f"[WARN] cached ics parse failed: {e}")
    return cache

def event_from_cache(raw_ical):
    """raw 바이트에서 VEVENT 객체를 새로 파싱해서 반환"""
    try:
        wrapped = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + raw_ical + b"\r\nEND:VCALENDAR"
        cal = Calendar.from_ical(wrapped)
        for component in cal.walk():
            if component.name == 'VEVENT':
                return component
    except ValueError as e:
        print(f"[WARN] event cache parse failed: {e}")
    return None

def get_ultra_short_base(now):
    """초단기예보 base_date/base_time 계산: 매시 30분 발표, +45분 버퍼"""
    buffered = now - timedelta(minutes=45)
    if buffered.minute >= 30:
        base = buffered.replace(minute=30, second=0, microsecond=0)
    else:
        base = buffered.replace(minute=30, second=0, microsecond=0) - timedelta(hours=1)
    return base.strftime('%Y%m%d'), base.strftime('%H%M')

def fetch_ultra_short_forecast(now):
    """초단기예보(0~6시간) 호출 → {date: {time: {category: value}}}"""
    base_date, base_time = get_ultra_short_base(now)
    url = (
        f"https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtFcst"
        f"?dataType=JSON&base_date={base_date}&base_time={base_time}"
        f"&nx={NX}&ny={NY}&numOfRows=200&authKey={API_KEY}"
    )
    res = fetch_api(url, label=f"초단기예보@{base_date}{base_time}")
    fmap = {}
    if not res or 'body' not in res.get('response', {}):
        return fmap
    for it in res['response']['body']['items']['item']:
        d, t, cat, val = it['fcstDate'], it['fcstTime'], it['category'], it['fcstValue']
        fmap.setdefault(d, {}).setdefault(t, {})[cat] = val
    return fmap

def fetch_warnings(now):
    """현재 발효 중인 기상특보 목록 조회 (text/CSV 응답)"""
    tm_str = now.strftime('%Y%m%d%H%M')
    url = (
        f"https://apihub.kma.go.kr/api/typ01/url/wrn_now_data_new.php"
        f"?fe=e&tm={tm_str}&disp=1&help=0&authKey={API_KEY}"
    )
    warnings = []
    try:
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            print(f"[WARN] 기상특보 HTTP {res.status_code}")
            return warnings
        text = res.text
    except requests.exceptions.RequestException as e:
        print(f"[WARN] 기상특보 요청 실패: {e}")
        return warnings

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # CSV 파싱 (disp=1) — 따옴표 제거
        parts = [p.strip().strip('"') for p in line.split(',')]
        if len(parts) < 9:
            continue
        try:
            warnings.append({
                'reg_up': parts[0],
                'reg_up_ko': parts[1],
                'reg_id': parts[2],
                'reg_ko': parts[3],
                'tm_fc': parts[4],
                'tm_ef': parts[5],
                'wrn': parts[6],
                'lvl': parts[7],
                'cmd': parts[8],
            })
        except IndexError:
            continue
    return warnings

def filter_warnings(warnings):
    """사용자 설정에 따라 특보 필터링.

    - WRN_KEYWORDS 가 있으면: REG_KO/REG_UP_KO 에 키워드 포함 시 매칭 (주의보+경보 모두)
    - 비어 있으면: 전국의 '경보' 등급만 표시 (또는 WRN_INCLUDE_WATCH='1'이면 주의보도)
    - 해제(CMD='해제' 등) 항목은 제외
    """
    out = []
    seen_uids = set()
    for w in warnings:
        # 해제 항목 제외
        if w['cmd'] and '해제' in w['cmd']:
            continue
        # 종류 코드가 매핑에 없으면 스킵 (지진해일 N 등 포함됨)
        if w['wrn'] not in WRN_INFO:
            continue
        is_match = False
        if WRN_KEYWORDS:
            haystack = f"{w['reg_ko']} {w['reg_up_ko']}"
            if any(kw in haystack for kw in WRN_KEYWORDS):
                is_match = True
        else:
            # 키워드 없으면 경보만 (또는 옵션에 따라 주의보 포함)
            if '경보' in w['lvl'] or WRN_INCLUDE_WATCH:
                is_match = True
        if not is_match:
            continue
        # 중복 제거 (같은 종류+수준+지역)
        uid = f"{w['wrn']}-{w['lvl']}-{w['reg_id']}"
        if uid in seen_uids:
            continue
        seen_uids.add(uid)
        out.append(w)
    return out

def _parse_kma_csv(text):
    """KMA apihub typ01 응답(disp=1 CSV) → 헤더+행 리스트.
    헤더가 #로 시작하는 마지막 행에 변수명이 있음."""
    rows = []
    headers = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            # 변수명 헤더 후보 (콤마 다수 포함)
            inner = line.lstrip('#').strip()
            if inner.count(',') >= 3:
                headers = [h.strip() for h in inner.split(',')]
            continue
        parts = [p.strip().strip('"') for p in line.split(',')]
        if not parts:
            continue
        rows.append(parts)
    return headers, rows


def fetch_earthquakes(now):
    """KMA apihub 지진 목록 (eqk_list.php). 최근 7일 + 규모 ≥ 2.0.

    출력 필드 (KMA spec): TP(3=국내,2=국외), TM_FC(발표), SEQ, TM_EQK(진앙시),
    MSC, MT(규모), LAT, LON, LOC, INT(진도), REM, COR
    """
    results = []
    tm_to = now.strftime('%Y%m%d%H%M')
    tm_from = (now - timedelta(days=7)).strftime('%Y%m%d%H%M')
    url = (
        "https://apihub.kma.go.kr/api/typ01/url/eqk_list.php"
        f"?tm1={tm_from}&tm2={tm_to}&disp=1&help=0&authKey={API_KEY}"
    )
    try:
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            print(f"[WARN] 지진 HTTP {res.status_code}")
            return results
        text = res.text
    except requests.exceptions.RequestException as e:
        print(f"[WARN] 지진 요청 실패: {e}")
        return results

    headers, rows = _parse_kma_csv(text)
    # 필드 인덱스 추정 (헤더 없으면 KMA spec 순서대로 fallback)
    def idx(name, default):
        try:
            return headers.index(name)
        except ValueError:
            return default
    i_tp, i_tmeqk = idx('TP', 0), idx('TM_EQK', 3)
    i_mt, i_lat, i_lon = idx('MT', 5), idx('LAT', 6), idx('LON', 7)
    i_loc, i_int = idx('LOC', 8), idx('INT', 9)

    seen = set()
    for parts in rows:
        if len(parts) <= max(i_tmeqk, i_mt, i_lat, i_lon, i_loc):
            continue
        try:
            tp = parts[i_tp] if i_tp < len(parts) else ''
            tm_dt = parse_kma_time(parts[i_tmeqk])
            mag = float(parts[i_mt])
            lat = float(parts[i_lat])
            lon = float(parts[i_lon])
            loc = parts[i_loc] if i_loc < len(parts) else ''
            intensity = parts[i_int] if i_int < len(parts) else ''
        except (ValueError, IndexError):
            continue
        if not tm_dt or mag < 2.0:
            continue
        # 중복 제거 (같은 시각+규모)
        key = (tm_dt.isoformat(), round(mag, 1))
        if key in seen:
            continue
        seen.add(key)
        results.append({
            'tp': tp, 'tm': tm_dt, 'lat': lat, 'lon': lon,
            'mag': mag, 'loc': loc, 'intensity': intensity,
        })
    return results


def fetch_typhoons(now):
    """KMA apihub typ_now.php — 기준시간 과거 12h 내 활성 태풍의 최근 분석+예측.

    출력 필드 (KMA spec): YY, SEQ, NOW(Y/N=진행여부), EFF(Y/N=한반도영향),
    TM_ST, TM_ED, TYP_NAME, TYP_EN, REM,
    FT(0=분석,1=예측), TYP, TMD, TYP_TM, FT_TM,
    LAT, LON, DIR(16방위), SP(km/h), PS(hPa), WS(m/s), RAD15, RAD25, RAD, LOC
    """
    results = []
    # tm: UTC 기준
    tm_utc = now.astimezone(pytz.UTC).strftime('%Y%m%d%H00')
    url = (
        "https://apihub.kma.go.kr/api/typ01/url/typ_now.php"
        f"?tm={tm_utc}&mode=2&disp=1&help=0&authKey={API_KEY}"
    )
    try:
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            print(f"[WARN] 태풍 HTTP {res.status_code}")
            return results
        text = res.text
    except requests.exceptions.RequestException as e:
        print(f"[WARN] 태풍 요청 실패: {e}")
        return results

    headers, rows = _parse_kma_csv(text)
    def idx(name, default):
        try:
            return headers.index(name)
        except ValueError:
            return default
    i_now, i_eff = idx('NOW', 2), idx('EFF', 3)
    i_name, i_ft = idx('TYP_NAME', 6), idx('FT', 9)
    i_lat, i_lon = idx('LAT', 14), idx('LON', 15)
    i_dir, i_sp = idx('DIR', 16), idx('SP', 17)
    i_ps, i_ws = idx('PS', 18), idx('WS', 19)
    i_loc = idx('LOC', 23)
    i_typtm = idx('TYP_TM', 12)

    # 활성 태풍별로 분석값 1개 + 예측값들 그룹화
    typhoons = {}
    for parts in rows:
        if len(parts) <= max(i_lon, i_ws):
            continue
        try:
            is_active = (parts[i_now] if i_now < len(parts) else '') == 'Y'
            ft = parts[i_ft] if i_ft < len(parts) else ''
            name = parts[i_name] if i_name < len(parts) else ''
            if not is_active or not name:
                continue
            entry = typhoons.setdefault(name, {
                'name': name,
                'eff': (parts[i_eff] if i_eff < len(parts) else '') == 'Y',
                'analysis': None, 'forecast': [],
            })
            point = {
                'tm': parse_kma_time(parts[i_typtm]) if i_typtm < len(parts) else None,
                'lat': float(parts[i_lat]) if parts[i_lat] else 0,
                'lon': float(parts[i_lon]) if parts[i_lon] else 0,
                'dir': parts[i_dir] if i_dir < len(parts) else '',
                'sp': float(parts[i_sp]) if i_sp < len(parts) and parts[i_sp] else 0,
                'ps': float(parts[i_ps]) if i_ps < len(parts) and parts[i_ps] else 0,
                'ws': float(parts[i_ws]) if i_ws < len(parts) and parts[i_ws] else 0,
                'loc': parts[i_loc] if i_loc < len(parts) else '',
            }
            if ft == '0':
                entry['analysis'] = point
            else:
                entry['forecast'].append(point)
        except (ValueError, IndexError):
            continue
    return list(typhoons.values())


def parse_kma_time(s):
    """KMA의 'YYYYMMDDHHMM' 또는 'YYYYMMDDHH' 문자열을 datetime으로"""
    s = str(s).strip()
    fmts = ['%Y%m%d%H%M', '%Y%m%d%H', '%Y%m%d']
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None

def grid_to_latlon(nx, ny):
    """KMA Lambert Conformal Conic 격자 → 위경도 역변환"""
    RE, GRID, SLAT1, SLAT2 = 6371.00877, 5.0, 30.0, 60.0
    OLON, OLAT, XO, YO = 126.0, 38.0, 43, 136
    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1, slat2 = SLAT1 * DEGRAD, SLAT2 * DEGRAD
    olon, olat = OLON * DEGRAD, OLAT * DEGRAD
    sn = math.tan(math.pi*0.25 + slat2*0.5) / math.tan(math.pi*0.25 + slat1*0.5)
    sn = math.log(math.cos(slat1)/math.cos(slat2)) / math.log(sn)
    sf = (math.tan(math.pi*0.25 + slat1*0.5)**sn) * math.cos(slat1) / sn
    ro = re*sf / (math.tan(math.pi*0.25 + olat*0.5)**sn)
    xn, yn = nx - XO, ro - ny + YO
    ra = math.sqrt(xn*xn + yn*yn)
    if sn < 0:
        ra = -ra
    alat = (re*sf/ra) ** (1.0/sn)
    alat = 2.0 * math.atan(alat) - math.pi*0.5
    if abs(xn) <= 0:
        theta = 0.0
    elif abs(yn) <= 0:
        theta = math.pi*0.5 * (-1 if xn < 0 else 1)
    else:
        theta = math.atan2(xn, yn)
    alon = theta/sn + olon
    return alat / DEGRAD, alon / DEGRAD


# --- 자연어 메시지 헬퍼 ---

def temp_comfort_message(temp):
    """기온 → 체감 메시지 (이모지 + 한 줄)"""
    try:
        t = float(temp)
    except (TypeError, ValueError):
        return ""
    if t >= 33: return "🥵 매우 더워요"
    if t >= 28: return "☀️ 더워요"
    if t >= 22: return "☀️ 따뜻해요"
    if t >= 15: return "😊 쾌적해요"
    if t >= 8:  return "🧥 선선해요"
    if t >= 0:  return "🥶 추워요"
    return "❄️ 매우 추워요"


# 보퍼트 풍력 계급 (m/s 기준)
BEAUFORT_TABLE = [
    (0.3,  "고요"),
    (1.6,  "실바람 — 연기가 천천히 흐름"),
    (3.4,  "남실바람 — 잎이 바스락거림"),
    (5.5,  "산들바람 — 잎과 작은 가지가 흔들림"),
    (8.0,  "건들바람 — 작은 가지가 흔들림"),
    (10.8, "흔들바람 — 작은 나무 흔들림"),
    (13.9, "된바람 — 큰 가지가 흔들림"),
    (17.2, "센바람 — 나무 전체가 흔들림"),
    (20.8, "큰바람 — 나뭇가지 부러짐"),
    (24.5, "큰센바람"),
    (28.5, "노대바람"),
    (32.7, "왕바람"),
]
def wind_message(wsd):
    try:
        v = float(wsd)
    except (TypeError, ValueError):
        return ""
    for limit, label in BEAUFORT_TABLE:
        if v <= limit:
            return label
    return "싹쓸바람"


def wind_direction_text(vec):
    """기상청 풍향(0~360°) → 16방위 한글"""
    try:
        deg = float(vec)
    except (TypeError, ValueError):
        return ""
    dirs = ["북", "북북동", "북동", "동북동", "동", "동남동", "남동", "남남동",
            "남", "남남서", "남서", "서남서", "서", "서북서", "북서", "북북서"]
    idx = int((deg + 11.25) / 22.5) % 16
    return dirs[idx]


def umbrella_message(pop, pty):
    """강수확률·강수형태 → 우산 추천 메시지"""
    try:
        p = int(pop)
    except (TypeError, ValueError):
        p = 0
    if str(pty) in {'1', '2', '4', '5'}:
        return f"☔ 우산 꼭 챙기세요 (비올 확률 {p}%)"
    if p >= 60:
        return f"🌂 우산 챙기세요 (비올 확률 {p}%)"
    if p >= 30:
        return f"🌂 우산 챙기는 게 안전해요 (비올 확률 {p}%)"
    return f"☀️ 우산 안 챙겨도 OK (비올 확률 {p}%)"


def find_next_rain(forecast_map, after_dt, seoul_tz):
    """forecast_map 에서 가장 가까운 비/눈 시각 반환 ('5월 12일 오후 3시' 형식)"""
    for d_str in sorted(forecast_map.keys()):
        day = forecast_map[d_str]
        for t_str in sorted(day.keys()):
            pty = str(day[t_str].get('PTY', '0'))
            if pty != '0':
                try:
                    dt = seoul_tz.localize(datetime.strptime(f"{d_str}{t_str}", '%Y%m%d%H%M'))
                except ValueError:
                    continue
                if dt < after_dt:
                    continue
                kind = {'1':'비','2':'비/눈','3':'눈','4':'소나기','5':'빗방울','6':'빗방울/눈날림','7':'눈날림'}.get(pty,'강수')
                hour = dt.hour
                ampm = '오전' if hour < 12 else '오후'
                hour12 = hour if hour <= 12 else hour - 12
                if hour == 0: hour12 = 12
                return f"{dt.month}월 {dt.day}일 {ampm} {hour12}시경 {kind}"
    return None


# --- 천문 계산 (astral + ephem) ---

# 달 위상 한글 (조도 % 기반 간이 매핑)
def moon_phase_korean(phase_index):
    """astral.moon.phase(): 0~27.99 (0=신월, 14=만월)"""
    if phase_index < 1.84566:  return "삭(신월)"
    if phase_index < 5.53699:  return "초승달"
    if phase_index < 9.22831:  return "상현달"
    if phase_index < 12.91963: return "하현전 차오름달"
    if phase_index < 16.61096: return "보름달"
    if phase_index < 20.30228: return "하현전 기우는달"
    if phase_index < 23.99361: return "하현달"
    if phase_index < 27.68493: return "그믐달"
    return "삭(신월)"


def moon_phase_emoji(phase_index):
    if phase_index < 1.84566:  return "🌑"
    if phase_index < 5.53699:  return "🌒"
    if phase_index < 9.22831:  return "🌓"
    if phase_index < 12.91963: return "🌔"
    if phase_index < 16.61096: return "🌕"
    if phase_index < 20.30228: return "🌖"
    if phase_index < 23.99361: return "🌗"
    return "🌘"


def compute_moon_times(lat, lon, day):
    """ephem 으로 월출/월몰 시각 (해당 day 기준 가장 가까운 시각)"""
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.date = day.strftime('%Y/%m/%d 00:00:00')
    moon = ephem.Moon()
    try:
        rise = ephem.localtime(obs.next_rising(moon))
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        rise = None
    obs.date = day.strftime('%Y/%m/%d 00:00:00')
    try:
        set_ = ephem.localtime(obs.next_setting(moon))
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        set_ = None
    return rise, set_


def compute_galactic_center_alt(lat, lon, when):
    """은하수 중심(궁수자리) 고도 계산"""
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.date = when.astimezone(pytz.UTC).strftime('%Y/%m/%d %H:%M:%S')
    # 은하수 중심 (Galactic Coordinate System Origin)
    # 적도좌표 ≈ RA 17h45m40s, Dec -29°00'28"
    gc = ephem.FixedBody()
    gc._ra = '17:45:40.04'
    gc._dec = '-29:00:28.1'
    gc._epoch = ephem.J2000
    gc.compute(obs)
    return math.degrees(float(gc.alt))


def format_time_kor(dt, ref_now):
    """datetime → '오늘 19:31' 또는 '내일 05:25'"""
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = pytz.timezone('Asia/Seoul').localize(dt)
    today = ref_now.date()
    label = "오늘" if dt.date() == today else ("내일" if dt.date() == today + timedelta(days=1) else dt.strftime('%m월 %d일'))
    return f"{label} {dt.strftime('%H:%M')}"


# --- 어제 비교 (단기예보 캐시에서 어제 기온 추출) ---

def extract_yesterday_max(cached_events_raw, yesterday_str):
    """캐시된 어제 단기예보 이벤트에서 SUMMARY 의 최고기온을 추출.
    포맷: '⛅ 14°C/24°C' or '⛅ 14°C/24°C 🟢🟡'"""
    if yesterday_str not in cached_events_raw:
        return None
    raw = cached_events_raw[yesterday_str].decode('utf-8', errors='ignore')
    # SUMMARY 라인의 'NN°C/NN°C' 패턴
    import re
    m = re.search(r'SUMMARY:[^\r\n]*?([\-\d]+)°C/([\-\d]+)°C', raw)
    if not m:
        return None
    try:
        return int(m.group(1)), int(m.group(2))
    except ValueError:
        return None


# --- 에어코리아 실시간 측정 (시도별) ---

def fetch_air_realtime(now):
    """시도별 실시간 측정치 (PM10/PM2.5/O3 μg/m³, ppm)"""
    if not DATA_GO_KR_KEY or not DATA_GO_KR_REGION:
        return {}
    # 시도명 매핑 (에어코리아 예보 지역 → 실시간 sidoName)
    SIDO_MAP = {
        '서울': '서울', '부산': '부산', '대구': '대구', '인천': '인천',
        '광주': '광주', '대전': '대전', '울산': '울산', '세종': '세종',
        '경기북부': '경기', '경기남부': '경기',
        '강원영서': '강원', '강원영동': '강원',
        '충북': '충북', '충남': '충남', '전북': '전북', '전남': '전남',
        '경북': '경북', '경남': '경남', '제주': '제주',
    }
    sido = SIDO_MAP.get(DATA_GO_KR_REGION, '서울')
    params = {
        'serviceKey': DATA_GO_KR_KEY,
        'returnType': 'json',
        'numOfRows': 100,
        'pageNo': 1,
        'sidoName': sido,
        'ver': '1.0',
    }
    try:
        res = requests.get(
            'https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty',
            params=params, timeout=15)
        if res.status_code != 200:
            print(f"[WARN] 에어코리아 실시간 HTTP {res.status_code}")
            return {}
        data = res.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"[WARN] 에어코리아 실시간 요청 실패: {e}")
        return {}
    items = (data.get('response', {}).get('body', {}) or {}).get('items') or []
    if not items:
        return {}
    # 시도 평균치 계산 (개별 측정소 평균)
    sums = {'PM10': [], 'PM25': [], 'O3': []}
    for it in items:
        for k_api, k_out in [('pm10Value','PM10'),('pm25Value','PM25'),('o3Value','O3')]:
            v = it.get(k_api)
            if v in (None, '-', ''):
                continue
            try:
                sums[k_out].append(float(v))
            except ValueError:
                continue
    out = {}
    for k, vs in sums.items():
        if vs:
            out[k] = round(sum(vs)/len(vs), 1)
    return out


def _living_base_time(now):
    """생활기상지수 API base_time: 06시 또는 18시 발표 중 가장 최신 (지연 30분 고려)"""
    eff = now - timedelta(minutes=30)
    if eff.hour >= 18:
        return eff.strftime('%Y%m%d') + '18'
    if eff.hour >= 6:
        return eff.strftime('%Y%m%d') + '06'
    return (eff - timedelta(days=1)).strftime('%Y%m%d') + '18'


def fetch_uv_index(now):
    """자외선 지수 — 현재/오늘 최대값 반환 (float 또는 None)"""
    if not DATA_GO_KR_KEY or not LIVING_AREA_NO:
        return None
    params = {
        'serviceKey': DATA_GO_KR_KEY,
        'dataType': 'JSON',
        'numOfRows': 10,
        'pageNo': 1,
        'areaNo': LIVING_AREA_NO,
        'time': _living_base_time(now),
    }
    try:
        res = requests.get(
            'https://apis.data.go.kr/1360000/LivingWthrIdxServiceV4/getUVIdxV4',
            params=params, timeout=15)
        if res.status_code != 200:
            print(f"[WARN] 자외선지수 HTTP {res.status_code}")
            return None
        data = res.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"[WARN] 자외선지수 요청 실패: {e}")
        return None
    items = (data.get('response', {}).get('body', {}) or {}).get('items') or {}
    item_list = items.get('item') if isinstance(items, dict) else items
    if not item_list:
        return None
    first = item_list[0] if isinstance(item_list, list) else item_list
    # h0, h3, h6, h9, ... 시간별 값 중 발표시각 기준 오늘 범위에서 max
    todays = []
    for k in ('h0','h3','h6','h9','h12','h15','h18','h21'):
        v = first.get(k)
        try:
            if v is not None: todays.append(float(v))
        except (TypeError, ValueError):
            continue
    if not todays:
        return None
    return max(todays)


def uv_grade(uv):
    if uv is None: return None, ''
    if uv < 3:  return '낮음', '🟢'
    if uv < 6:  return '보통', '🟡'
    if uv < 8:  return '높음', '🟠'
    if uv < 11: return '매우높음', '🔴'
    return '위험', '⚫'


def fetch_pollen_risk(now):
    """꽃가루 위험지수 — 참나무·소나무·잡초 중 최대 risk 반환"""
    if not DATA_GO_KR_KEY or not LIVING_AREA_NO:
        return None, None
    base_time = _living_base_time(now)
    endpoints = [
        ('getOakPollenRiskIdxV4', '참나무'),
        ('getPinePollenRiskIdxV4', '소나무'),
        ('getWeedsPollenRiskIdxV4', '잡초'),
    ]
    max_risk = None
    max_label = None
    for ep, name in endpoints:
        params = {
            'serviceKey': DATA_GO_KR_KEY,
            'dataType': 'JSON',
            'numOfRows': 10,
            'pageNo': 1,
            'areaNo': LIVING_AREA_NO,
            'time': base_time,
        }
        try:
            res = requests.get(f'https://apis.data.go.kr/1360000/HealthWthrIdxServiceV4/{ep}',
                               params=params, timeout=15)
            if res.status_code != 200:
                continue
            data = res.json()
        except (requests.exceptions.RequestException, ValueError):
            continue
        items = (data.get('response', {}).get('body', {}) or {}).get('items') or {}
        item_list = items.get('item') if isinstance(items, dict) else items
        if not item_list:
            continue
        first = item_list[0] if isinstance(item_list, list) else item_list
        v = first.get('today') or first.get('h0')
        try:
            risk = int(v)
        except (TypeError, ValueError):
            continue
        if max_risk is None or risk > max_risk:
            max_risk = risk
            max_label = name
    return max_risk, max_label


def pollen_grade(risk):
    if risk is None: return None, ''
    if risk == 0: return '낮음', '🟢'
    if risk == 1: return '보통', '🟡'
    if risk == 2: return '높음', '🟠'
    return '매우높음', '🔴'


def pm10_grade(val):
    if val is None: return None, ''
    if val <= 30:  return '좋음', '🟢'
    if val <= 80:  return '보통', '🟡'
    if val <= 150: return '나쁨', '🟠'
    return '매우나쁨', '🔴'

def pm25_grade(val):
    if val is None: return None, ''
    if val <= 15:  return '좋음', '🟢'
    if val <= 35:  return '보통', '🟡'
    if val <= 75:  return '나쁨', '🟠'
    return '매우나쁨', '🔴'

def o3_grade(val):
    if val is None: return None, ''
    # ppm
    if val <= 0.03: return '좋음', '🟢'
    if val <= 0.09: return '보통', '🟡'
    if val <= 0.15: return '나쁨', '🟠'
    return '매우나쁨', '🔴'


def parse_inform_grade(grade_str, region):
    """에어코리아 informGrade 문자열에서 region 등급 추출.
    포맷: '서울 : 보통,제주 : 보통,...'

    API는 '영서'/'영동'으로 응답하지만 사용자는 '강원영서'/'강원영동' 으로 입력할 수 있어
    호환 매핑을 적용함."""
    if not grade_str:
        return None
    # 사용자 입력 정규화
    region_aliases = {
        '강원영서': '영서',
        '강원영동': '영동',
    }
    target = region_aliases.get(region, region)
    for chunk in grade_str.split(','):
        parts = chunk.split(':')
        if len(parts) != 2:
            continue
        area, level = parts[0].strip(), parts[1].strip()
        if area == target:
            return level
    return None

def fetch_air_forecast(now):
    """에어코리아 대기오염예보 — PM10/PM25 등급을 날짜별로 반환.

    반환: {'YYYYMMDD': {'PM10': '보통', 'PM25': '좋음'}, ...}
    """
    result = {}
    if not DATA_GO_KR_KEY or not DATA_GO_KR_REGION:
        return result
    today_ymd = now.strftime('%Y-%m-%d')
    for code in ('PM10', 'PM25'):
        params = {
            'serviceKey': DATA_GO_KR_KEY,
            'returnType': 'json',
            'numOfRows': 100,
            'pageNo': 1,
            'searchDate': today_ymd,   # 빈 문자열 대신 명시적 날짜
            'InformCode': code,          # 카멜 케이스 첫글자 대문자가 정확 (doc spec)
        }
        try:
            res = requests.get(
                'https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMinuDustFrcstDspth',
                params=params, timeout=15)
            if res.status_code != 200:
                print(f"[WARN] 에어코리아 {code} HTTP {res.status_code}")
                continue
            data = res.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"[WARN] 에어코리아 {code} 요청 실패: {e}")
            continue
        items = (data.get('response', {}).get('body', {}) or {}).get('items') or []
        if not items:
            print(f"[WARN] 에어코리아 {code} 응답 비어 있음")
            continue
        for it in items:
            inform_date = it.get('informData', '').replace('-', '')
            grade_str = it.get('informGrade', '')
            grade = parse_inform_grade(grade_str, DATA_GO_KR_REGION)
            if not inform_date or not grade:
                continue
            result.setdefault(inform_date, {})[code] = grade
    return result

def main():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    today_str = now.strftime('%Y%m%d')
    update_ts = now.strftime('%Y-%m-%d %H:%M:%S')

    today_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    short_end_str = (today_dt + timedelta(days=3)).strftime('%Y%m%d')  # D+0~D+3 단기
    mid_start_dt  = today_dt + timedelta(days=4)                        # D+4부터 중기
    mid_end_dt    = today_dt + timedelta(days=10)                       # D+10까지

    cal = Calendar()
    cal.add('prodid', '-//redchupa//weather-calendar//KR')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('X-WR-CALNAME', '기상청 날씨')
    cal.add('X-WR-TIMEZONE', 'Asia/Seoul')
    processed_dates = set()

    # --- [2. 기존 캐시 로드] ---
    cached_events = load_cached_events('weather.ics')
    print("캐시된 날짜들:", sorted(cached_events.keys()))

    # --- [3. 단기 예보: D+0 ~ D+3 시간별 상세] ---
    base_date, base_time = get_base_datetime(now)
    url_short = (
        f"https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst"
        f"?dataType=JSON&base_date={base_date}&base_time={base_time}"
        f"&nx={NX}&ny={NY}&numOfRows=1000&authKey={API_KEY}"
    )
    forecast_map = {}
    short_res = fetch_api(url_short, label="단기예보")
    if short_res and 'body' in short_res['response']:
        for it in short_res['response']['body']['items']['item']:
            d, t, cat, val = it['fcstDate'], it['fcstTime'], it['category'], it['fcstValue']
            if d not in forecast_map: forecast_map[d] = {}
            if t not in forecast_map[d]: forecast_map[d][t] = {}
            forecast_map[d][t][cat] = val

    # 초단기예보로 가까운 0~6시간 정밀도 향상 (T1H→TMP 등 카테고리 매핑)
    ultra_map = fetch_ultra_short_forecast(now)
    ULTRA_CAT_MAP = {'T1H': 'TMP', 'RN1': 'PCP', 'SKY': 'SKY', 'PTY': 'PTY', 'REH': 'REH', 'WSD': 'WSD', 'VEC': 'VEC'}
    ultra_count = 0
    for d_str, day in ultra_map.items():
        for t_str, cats in day.items():
            for src, dst in ULTRA_CAT_MAP.items():
                if src in cats:
                    forecast_map.setdefault(d_str, {}).setdefault(t_str, {})[dst] = cats[src]
                    ultra_count += 1
    if ultra_count:
        print(f"초단기예보 적용: {ultra_count}개 값 갱신")

    # 미세먼지/초미세먼지 예보 — 오늘/내일/모레 (있을 경우)
    air_forecast = fetch_air_forecast(now)
    if not DATA_GO_KR_KEY or not DATA_GO_KR_REGION:
        print("미세먼지 예보: DATA_GO_KR_KEY 또는 DATA_GO_KR_REGION 미설정 → 건너뜀")
    elif air_forecast:
        print(f"미세먼지 예보 ({DATA_GO_KR_REGION}): {len(air_forecast)}일치 수집")
    else:
        print(f"미세먼지 예보 ({DATA_GO_KR_REGION}): 데이터 없음 — 지역명 오타 또는 API 응답 확인 필요")

    # --- 풍부한 description 빌더용 사전계산 ---
    LAT, LON = grid_to_latlon(NX, NY)
    print(f"위경도 변환: NX={NX},NY={NY} → lat={LAT:.4f}, lon={LON:.4f}")
    air_rt = fetch_air_realtime(now)
    if air_rt:
        print(f"실시간 대기질: PM10={air_rt.get('PM10','-')}, PM25={air_rt.get('PM25','-')}, O3={air_rt.get('O3','-')}")
    uv_today = fetch_uv_index(now)
    if uv_today is not None:
        print(f"자외선지수: {uv_today}")
    elif LIVING_AREA_NO:
        print(f"자외선지수: 데이터 없음 (areaNo={LIVING_AREA_NO})")
    else:
        print("자외선지수: LIVING_AREA_NO 미설정 → 건너뜀")
    pollen_max_risk, pollen_label = fetch_pollen_risk(now)
    if pollen_max_risk is not None:
        print(f"꽃가루 ({pollen_label}): risk={pollen_max_risk}")
    yesterday_str = (today_dt - timedelta(days=1)).strftime('%Y%m%d')
    y_minmax = extract_yesterday_max(cached_events, yesterday_str)

    # 오늘 AM/PM 대표 날씨 추출
    def _am_pm_weather(day_data):
        am_skies, pm_skies = [], []
        am_pty, pm_pty = [], []
        for t_str, cats in day_data.items():
            try:
                h = int(t_str[:2])
            except ValueError:
                continue
            sky, pty = cats.get('SKY'), cats.get('PTY')
            if h < 12:
                if sky: am_skies.append(sky)
                if pty: am_pty.append(pty)
            else:
                if sky: pm_skies.append(sky)
                if pty: pm_pty.append(pty)
        def _rep(skies, ptys):
            if not skies: return None
            # 강수가 한 번이라도 있으면 그것이 우선
            rain_p = next((p for p in ptys if p != '0'), '0')
            if rain_p != '0':
                return get_weather_info('1', rain_p)
            # 가장 흔한 SKY
            from collections import Counter
            sky = Counter(skies).most_common(1)[0][0]
            return get_weather_info(sky, '0')
        return _rep(am_skies, am_pty), _rep(pm_skies, pm_pty)

    cache = {'TMP': '15', 'SKY': '1', 'PTY': '0', 'REH': '50', 'WSD': '1.0', 'POP': '0', 'VEC': '0'}
    for d_str in sorted(forecast_map.keys()):
        if d_str < today_str or d_str > short_end_str:
            continue
        day_data = forecast_map[d_str]
        tmps = [float(day_data[t]['TMP']) for t in day_data if 'TMP' in day_data[t]]
        if not tmps: continue
        t_min, t_max = int(min(tmps)), int(max(tmps))
        rep_t = '1200' if '1200' in day_data else sorted(day_data.keys())[0]
        rep_emoji, rep_label = get_weather_info(
            day_data[rep_t].get('SKY', cache['SKY']),
            day_data[rep_t].get('PTY', cache['PTY'])
        )

        # 시간별 슬롯 + 현재 시점에 가까운 데이터 기록
        hourly_lines = []
        has_future_data = False
        current_snap = None  # 가장 가까운 미래/현재 슬롯 데이터
        for h in range(24):
            t_str = f"{h:02d}00"
            event_time = seoul_tz.localize(datetime.strptime(f"{d_str}{t_str}", '%Y%m%d%H%M'))
            if t_str in day_data:
                for cat in cache.keys():
                    if cat in day_data[t_str]: cache[cat] = day_data[t_str][cat]
            if event_time >= now:
                emoji, wf_str = get_weather_info(cache['SKY'], cache['PTY'])
                details = []
                if cache['PTY'] != '0':
                    details.append(f"☔{cache['POP']}%")
                details.append(f"💧{cache['REH']}%")
                details.append(f"🚩{cache['WSD']}m/s")
                hourly_lines.append(f"[{t_str[:2]}시] {emoji} {wf_str} {cache['TMP']}°C ({' '.join(details)})")
                has_future_data = True
                if current_snap is None:
                    current_snap = dict(cache)
        if not has_future_data: continue

        # 미세먼지 예보 등급 (오늘/내일/모레용)
        air_today = air_forecast.get(d_str, {})
        pm10_fcst = air_today.get('PM10')
        pm25_fcst = air_today.get('PM25')
        pm10_em = PM_GRADE_EMOJI.get(pm10_fcst, '')
        pm25_em = PM_GRADE_EMOJI.get(pm25_fcst, '')
        summary_suffix = f" {pm10_em}{pm25_em}" if (pm10_em or pm25_em) else ""

        # ─── 오늘 이벤트는 풍부한 description ───
        if d_str == today_str:
            am_w, pm_w = _am_pm_weather(day_data)
            snap = current_snap or cache
            now_emoji, now_label = get_weather_info(snap['SKY'], snap['PTY'])
            wind_dir = wind_direction_text(snap.get('VEC', '0'))
            wind_dir_text = f"({wind_dir}쪽에서) " if wind_dir else ""
            wind_lbl = wind_message(snap['WSD'])

            desc_lines = []
            desc_lines.append(f"📍 {LOCATION_NAME} 날씨 (위경도 {LAT:.3f}, {LON:.3f})")
            desc_lines.append("")
            desc_lines.append(f"{now_emoji} 지금 날씨: {now_label}")
            desc_lines.append(f"기온: {snap['TMP']}°C ({temp_comfort_message(snap['TMP'])})")
            desc_lines.append(f"최고 온도: {t_max}°C / 최저 온도: {t_min}°C")
            desc_lines.append(f"습도: {snap['REH']}%")
            desc_lines.append(f"바람: {snap['WSD']} m/s ({wind_lbl}) {wind_dir_text}")
            if am_w and pm_w:
                desc_lines.append(f"오전 날씨: {am_w[0]} {am_w[1]} / 오후 날씨: {pm_w[0]} {pm_w[1]}")
            desc_lines.append(f"오늘은 {umbrella_message(snap['POP'], snap['PTY'])}")
            nr = find_next_rain(forecast_map, now, seoul_tz)
            desc_lines.append(f"다음 비🌧 : {nr}" if nr else "다음 비🌧 : 예보 기간 내 강수 없음")
            if y_minmax:
                diff = t_max - y_minmax[1]
                arrow = "높아요" if diff > 0 else ("낮아요" if diff < 0 else "같아요")
                desc_lines.append(f"어제와 비교: 최고기온이 어제보다 {abs(diff)}°{arrow}")

            # 대기질 (실측 + 예보)
            desc_lines.append("")
            if air_rt:
                p10 = air_rt.get('PM10'); p10_l, p10_e = pm10_grade(p10)
                p25 = air_rt.get('PM25'); p25_l, p25_e = pm25_grade(p25)
                o3 = air_rt.get('O3'); o3_l, o3_e = o3_grade(o3)
                if p10_l == '좋음' and p25_l == '좋음':
                    desc_lines.append("😊 오늘 공기는 깨끗해요")
                elif (p10_l == '나쁨' or p25_l == '나쁨' or p10_l == '매우나쁨' or p25_l == '매우나쁨'):
                    desc_lines.append("😷 오늘 공기는 안 좋아요 — 마스크 권장")
                else:
                    desc_lines.append("🙂 오늘 공기는 보통이에요")
                desc_lines.append(f"미세먼지 (PM10): {p10} ㎍/㎥ ({p10_e} {p10_l})")
                desc_lines.append(f"초미세먼지 (PM2.5): {p25} ㎍/㎥ ({p25_e} {p25_l})")
                if o3_l:
                    desc_lines.append(f"오존(O₃): {o3} ppm ({o3_e} {o3_l})")
            elif pm10_fcst or pm25_fcst:
                desc_lines.append(f"미세먼지 예보 ({DATA_GO_KR_REGION}): {pm10_em} PM10 {pm10_fcst or '-'} / {pm25_em} PM2.5 {pm25_fcst or '-'}")

            # 자외선·꽃가루
            if uv_today is not None:
                uv_l, uv_e = uv_grade(uv_today)
                desc_lines.append(f"자외선 (오늘 최대): {uv_today:.1f} ({uv_e} {uv_l})")
            if pollen_max_risk is not None:
                pl_l, pl_e = pollen_grade(pollen_max_risk)
                desc_lines.append(f"꽃가루 ({pollen_label}): {pl_e} {pl_l}")

            # 내일 미리보기
            tomorrow_str = (today_dt + timedelta(days=1)).strftime('%Y%m%d')
            if tomorrow_str in forecast_map:
                tdata = forecast_map[tomorrow_str]
                t_tmps = [float(tdata[t]['TMP']) for t in tdata if 'TMP' in tdata[t]]
                if t_tmps:
                    tt_min, tt_max = int(min(t_tmps)), int(max(t_tmps))
                    t_am, t_pm = _am_pm_weather(tdata)
                    rep_t2 = '1200' if '1200' in tdata else sorted(tdata.keys())[0]
                    t_emoji, _ = get_weather_info(tdata[rep_t2].get('SKY','1'), tdata[rep_t2].get('PTY','0'))
                    desc_lines.append("")
                    desc_lines.append(f"{t_emoji} 내일은?")
                    desc_lines.append(f"최고 {tt_max}°C ({temp_comfort_message(tt_max)}) / 최저 {tt_min}°C ({temp_comfort_message(tt_min)})")
                    if t_am and t_pm:
                        desc_lines.append(f"오전: {t_am[0]} {t_am[1]} / 오후: {t_pm[0]} {t_pm[1]}")

            # 천문 — 해
            try:
                city = LocationInfo("KR", "KR", "Asia/Seoul", LAT, LON)
                s_today = sun(city.observer, date=now.date(), tzinfo=seoul_tz)
                s_tomo = sun(city.observer, date=now.date()+timedelta(days=1), tzinfo=seoul_tz)
                desc_lines.append("")
                desc_lines.append("☀️ 오늘 해는?")
                desc_lines.append(f"🌅 일출: {format_time_kor(s_today['sunrise'], now)}")
                desc_lines.append(f"🌇 일몰: {format_time_kor(s_today['sunset'], now)}")
                # 시민박명 (Civil twilight)
                cd_morn = astral_dawn(city.observer, date=now.date(), tzinfo=seoul_tz, depression=6)
                cd_eve  = astral_dusk(city.observer, date=now.date(), tzinfo=seoul_tz, depression=6)
                desc_lines.append(f"🌆 시민박명: {format_time_kor(cd_morn, now)} ~ {format_time_kor(cd_eve, now)}")
                # 천문박명 (Astronomical twilight)
                ad_morn = astral_dawn(city.observer, date=now.date(), tzinfo=seoul_tz, depression=18)
                ad_eve  = astral_dusk(city.observer, date=now.date(), tzinfo=seoul_tz, depression=18)
                desc_lines.append(f"🌃 천문박명: {format_time_kor(ad_morn, now)} ~ {format_time_kor(ad_eve, now)}")

                # 달
                phase_idx = moon.phase(now.date())
                illum = abs(math.cos(phase_idx / 29.53 * 2 * math.pi)) * 100  # 대략적 조도
                # 더 정확한 조도는 ephem
                mobs = ephem.Observer(); mobs.lat, mobs.lon = str(LAT), str(LON)
                mobs.date = now.astimezone(pytz.UTC).strftime('%Y/%m/%d %H:%M:%S')
                m_body = ephem.Moon(mobs)
                illum = float(m_body.phase)
                desc_lines.append("")
                desc_lines.append(f"{moon_phase_emoji(phase_idx)} 달은?")
                desc_lines.append(f"위상: {moon_phase_korean(phase_idx)} (조도 {illum:.0f}%)")
                m_rise, m_set = compute_moon_times(LAT, LON, now.date())
                desc_lines.append(f"🌒 월출: {format_time_kor(m_rise, now)}")
                desc_lines.append(f"🌘 월몰: {format_time_kor(m_set, now)}")

                # 은하수
                gc_alt = compute_galactic_center_alt(LAT, LON, now)
                moon_alt = math.degrees(float(m_body.alt))
                in_night = ad_eve < now < (ad_morn + timedelta(days=1))
                desc_lines.append("")
                desc_lines.append("🌌 은하수 추적")
                if gc_alt < 0:
                    desc_lines.append(f"🔭 지금 상황: 관측불가 — 지평선 아래 (고도 {gc_alt:.1f}°)")
                elif not in_night:
                    desc_lines.append(f"🔭 지금 상황: 관측불가 — 아직 충분히 어둡지 않음 (고도 {gc_alt:.1f}°)")
                elif illum > 70:
                    desc_lines.append(f"🔭 지금 상황: 관측불리 — 달이 밝음 (고도 {gc_alt:.1f}°, 달 조도 {illum:.0f}%)")
                else:
                    desc_lines.append(f"🔭 지금 상황: 관측 가능 — 은하수 고도 {gc_alt:.1f}°")
                desc_lines.append(f"달 고도: {moon_alt:.1f}°")
                desc_lines.append(f"⏰ 오늘 밤 관측 가능 시간대: {format_time_kor(ad_eve, now)} ~ {format_time_kor(ad_morn + timedelta(days=1), now)}")
            except Exception as e:
                print(f"[WARN] 천문 계산 실패: {e}")

            # 시간별 상세 (접혀 보이는 캘린더 앱이 많아서 마지막에)
            desc_lines.append("")
            desc_lines.append("⏱ 시간별 상세")
            desc_lines.extend(hourly_lines)
            desc_lines.append("")
            desc_lines.append(f"📊 최종 업데이트: {update_ts} (KST)")
            description = "\n".join(desc_lines)
        else:
            # 오늘 외 D+1~D+3: 기존 간단 포맷
            desc_lines = []
            if pm10_em or pm25_em:
                desc_lines.append(f"🌫️ 미세 {pm10_em} {pm10_fcst or '-'} / 초미세 {pm25_em} {pm25_fcst or '-'}\n")
            desc_lines.extend(hourly_lines)
            desc_lines.append(f"\n최종 업데이트: {update_ts} (KST)")
            description = "\n".join(desc_lines)

        event = Event()
        event.add('dtstamp', now)
        event.add('summary', f"{rep_emoji} {t_min}°C/{t_max}°C{summary_suffix}")
        event.add('location', LOCATION_NAME)
        event.add('description', description)
        event.add('dtstart', datetime.strptime(d_str, '%Y%m%d').date())
        event.add('dtend', datetime.strptime(d_str, '%Y%m%d').date() + timedelta(days=1))
        event.add('uid', f"{d_str}@short_summary")
        cal.add_component(event)
        processed_dates.add(d_str)

    # 단기 API 실패시 D+0~D+3 캐시 재사용
    for delta in range(4):
        d_str = (today_dt + timedelta(days=delta)).strftime('%Y%m%d')
        if d_str not in processed_dates and d_str in cached_events:
            event = event_from_cache(cached_events[d_str])
            if event:
                cal.add_component(event)
                processed_dates.add(d_str)

    # --- [4. 중기 예보: D+4 ~ D+10] ---
    tmfc_candidates = get_tmfc_candidates(now)
    t_res, l_res, tm_fc_dt = None, None, None
    for candidate in tmfc_candidates:
        tm_fc_str = candidate.strftime('%Y%m%d%H%M')
        url_mid_temp = (
            f"https://apihub.kma.go.kr/api/typ02/openApi/MidFcstInfoService/getMidTa"
            f"?dataType=JSON&regId={REG_ID_TEMP}&tmFc={tm_fc_str}&authKey={API_KEY}"
        )
        url_mid_land = (
            f"https://apihub.kma.go.kr/api/typ02/openApi/MidFcstInfoService/getMidLandFcst"
            f"?dataType=JSON&regId={REG_ID_LAND}&tmFc={tm_fc_str}&authKey={API_KEY}"
        )
        t_try = fetch_api(url_mid_temp, label=f"중기기온@{tm_fc_str}")
        l_try = fetch_api(url_mid_land, label=f"중기육상@{tm_fc_str}")
        if t_try and l_try:
            t_res, l_res, tm_fc_dt = t_try, l_try, candidate
            break

    t_items, l_items = None, None
    if t_res and l_res and tm_fc_dt:
        try:
            t_items = t_res['response']['body']['items']['item'][0]
            l_items = l_res['response']['body']['items']['item'][0]
        except (KeyError, IndexError, TypeError):
            pass

    # D+4 ~ D+10 순서대로 채우기
    cur_dt = mid_start_dt
    while cur_dt <= mid_end_dt:
        d_str = cur_dt.strftime('%Y%m%d')
        event = None

        # 1순위: 새 중기 데이터
        if t_items and l_items and tm_fc_dt:
            field_i = (cur_dt.date() - tm_fc_dt.date()).days
            t_min = t_items.get(f'taMin{field_i}')
            t_max = t_items.get(f'taMax{field_i}')
            wf_rep = l_items.get(f'wf{field_i}Pm') if field_i <= 7 else l_items.get(f'wf{field_i}')

            if t_min is not None and t_max is not None and wf_rep is not None:
                mid_desc = []
                if field_i <= 7:
                    wf_am = l_items.get(f'wf{field_i}Am')
                    wf_pm = l_items.get(f'wf{field_i}Pm')
                    rn_am = l_items.get(f'rnSt{field_i}Am')
                    rn_pm = l_items.get(f'rnSt{field_i}Pm')
                    mid_desc.append(f"[오전] {get_mid_emoji(wf_am)} {wf_am} (☔{rn_am}%)")
                    mid_desc.append(f"[오후] {get_mid_emoji(wf_pm)} {wf_pm} (☔{rn_pm}%)")
                else:
                    wf_val = l_items.get(f'wf{field_i}')
                    rn_st  = l_items.get(f'rnSt{field_i}')
                    mid_desc.append(f"[종일] {get_mid_emoji(wf_val)} {wf_val} (☔{rn_st}%)")
                mid_desc.append(f"\n최종 업데이트: {update_ts} (KST)")

                event = Event()
                event.add('dtstamp', now)
                event.add('summary', f"{get_mid_emoji(wf_rep)} {t_min}/{t_max}°C")
                event.add('location', LOCATION_NAME)
                event.add('description', "\n".join(mid_desc))
                event.add('dtstart', cur_dt.date())
                event.add('dtend', (cur_dt + timedelta(days=1)).date())
                event.add('uid', f"{d_str}@mid")

        # 2순위: 캐시 재사용
        if event is None and d_str in cached_events:
            event = event_from_cache(cached_events[d_str])

        if event is not None:
            cal.add_component(event)
            processed_dates.add(d_str)

        cur_dt += timedelta(days=1)

    # --- [5. 기상특보] ---
    warnings_raw = fetch_warnings(now)
    warnings = filter_warnings(warnings_raw)
    print(f"기상특보: 총 {len(warnings_raw)}건 중 {len(warnings)}건 표시")

    warning_count = 0
    for w in warnings:
        emoji, name = WRN_INFO.get(w['wrn'], ('⚠️', w['wrn']))
        level_emoji = '🚨' if '경보' in w['lvl'] else '⚠️'
        # 발효 시각
        tm_ef_dt = parse_kma_time(w['tm_ef'])
        if not tm_ef_dt:
            continue
        ef_local = seoul_tz.localize(tm_ef_dt) if tm_ef_dt.tzinfo is None else tm_ef_dt
        # 종료 시각이 없으므로 발효일 기준 1일 길이로 잡고, 캘린더 앱이 갱신될 때마다 다시 그려짐
        ev = Event()
        ev.add('dtstamp', now)
        ev.add('summary', f"{level_emoji} {emoji} {name}{w['lvl']} ({w['reg_ko']})")
        ev.add('description',
                f"발효: {ef_local.strftime('%Y-%m-%d %H:%M')} (KST)\n"
                f"발표: {w['tm_fc']}\n"
                f"지역: {w['reg_up_ko']} > {w['reg_ko']}\n"
                f"종류: {name} {w['lvl']}\n"
                f"\n최종 업데이트: {update_ts} (KST)")
        ev.add('location', w['reg_ko'])
        ev.add('dtstart', ef_local.date())
        ev.add('dtend', ef_local.date() + timedelta(days=1))
        ev.add('uid', f"wrn-{w['reg_id']}-{w['wrn']}-{w['tm_fc']}@kma")
        ev.add('categories', 'WEATHER_ALERT')
        cal.add_component(ev)
        warning_count += 1

    # --- [6. 지진] ---
    quakes = fetch_earthquakes(now)
    print(f"지진: 최근 7일 내 {len(quakes)}건 (규모 ≥ 2.0)")
    quake_count = 0
    for q in quakes:
        if q['mag'] < 3.0:
            continue  # 캘린더엔 규모 3.0 이상만
        tm_local = seoul_tz.localize(q['tm']) if q['tm'].tzinfo is None else q['tm']
        # 국내(TP=3) 강조
        emoji = '🚨🌋' if q['tp'] == '3' else '🌋'
        kind = '국내' if q['tp'] == '3' else '국외'
        ev = Event()
        ev.add('dtstamp', now)
        ev.add('summary', f"{emoji} {kind}지진 M{q['mag']:.1f} ({q['loc']})")
        desc = [
            f"발생: {tm_local.strftime('%Y-%m-%d %H:%M')} (KST)",
            f"종류: {kind}지진",
            f"규모: M{q['mag']:.1f}",
            f"위치: {q['loc']}",
            f"위경도: {q['lat']:.3f}, {q['lon']:.3f}",
        ]
        if q['intensity']:
            desc.append(f"진도: {q['intensity']}")
        desc.append(f"\n최종 업데이트: {update_ts} (KST)")
        ev.add('description', "\n".join(desc))
        ev.add('location', q['loc'])
        ev.add('dtstart', tm_local.date())
        ev.add('dtend', tm_local.date() + timedelta(days=1))
        ev.add('uid', f"eqk-{tm_local.strftime('%Y%m%d%H%M%S')}-{int(q['mag']*10)}@kma")
        ev.add('categories', 'EARTHQUAKE')
        cal.add_component(ev)
        quake_count += 1

    # --- [7. 태풍] ---
    typhoons = fetch_typhoons(now)
    print(f"태풍: 현재 활성 {len(typhoons)}건")
    typhoon_count = 0
    for t in typhoons:
        analysis = t.get('analysis')
        forecasts = t.get('forecast', [])
        if not analysis:
            # 분석값 없으면 예측 첫 항목으로 대체
            if not forecasts:
                continue
            analysis = forecasts[0]
        # 한반도 영향 여부 강조
        eff_emoji = '🚨🌀' if t['eff'] else '🌀'
        eff_text = '한반도 영향' if t['eff'] else '북서태평양'
        ev = Event()
        ev.add('dtstamp', now)
        ev.add('summary', f"{eff_emoji} 태풍 {t['name']} {analysis['ws']:.0f}m/s ({eff_text})")
        desc = [
            f"태풍명: {t['name']}",
            f"한반도 영향: {'예' if t['eff'] else '아니오 (현재 기준)'}",
            f"현재 위치: lat {analysis['lat']:.2f}, lon {analysis['lon']:.2f}",
        ]
        if analysis.get('loc'):
            desc.append(f"위치명: {analysis['loc']}")
        desc.append(f"중심기압: {analysis['ps']:.0f} hPa")
        desc.append(f"최대풍속: {analysis['ws']:.1f} m/s")
        if analysis.get('dir') and analysis.get('sp'):
            desc.append(f"진행방향/속도: {analysis['dir']} 방향 {analysis['sp']:.0f} km/h")
        if forecasts:
            desc.append("\n📍 예측 진로:")
            for fp in forecasts[:6]:  # 최대 6개 시각만
                if fp.get('tm'):
                    desc.append(f"  · {fp['tm'].strftime('%m/%d %H시')} UTC → lat {fp['lat']:.1f}, lon {fp['lon']:.1f}, {fp['ws']:.0f}m/s")
        desc.append(f"\n최종 업데이트: {update_ts} (KST)")
        ev.add('description', "\n".join(desc))
        ev.add('dtstart', now.date())
        ev.add('dtend', now.date() + timedelta(days=1))
        ev.add('uid', f"typ-{t['name']}-{now.strftime('%Y%m%d')}@kma")
        ev.add('categories', 'TYPHOON')
        cal.add_component(ev)
        typhoon_count += 1

    print("최종 processed_dates:", sorted(processed_dates))
    print(f"기상특보 이벤트: {warning_count}건 추가, 지진: {quake_count}건, 태풍: {typhoon_count}건")
    with open('weather.ics', 'wb') as f:
        f.write(cal.to_ical())

    # 오늘 날씨 요약을 워크플로우 commit message용으로 노출
    today_summary = ""
    if today_str in forecast_map:
        day_data = forecast_map[today_str]
        tmps = [float(day_data[t]['TMP']) for t in day_data if 'TMP' in day_data[t]]
        if tmps:
            t_min, t_max = int(min(tmps)), int(max(tmps))
            rep_t = '1200' if '1200' in day_data else sorted(day_data.keys())[0]
            rep_emoji, rep_label = get_weather_info(
                day_data[rep_t].get('SKY', '1'),
                day_data[rep_t].get('PTY', '0')
            )
            today_summary = f"{rep_emoji} {rep_label} {t_min}/{t_max}°C"
            print(f"오늘 요약: {today_summary}")

    gh_output = os.environ.get('GITHUB_OUTPUT')
    if gh_output and today_summary:
        with open(gh_output, 'a', encoding='utf-8') as f:
            f.write(f"summary={today_summary}\n")

if __name__ == "__main__":
    main()
