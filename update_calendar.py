import os
import requests
import pytz
from datetime import datetime, timedelta
from icalendar import Calendar, Event

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

def parse_inform_grade(grade_str, region):
    """에어코리아 informGrade 문자열에서 region 등급 추출.
    포맷: '서울 : 보통,제주 : 보통,...'"""
    if not grade_str:
        return None
    for chunk in grade_str.split(','):
        parts = chunk.split(':')
        if len(parts) != 2:
            continue
        area, level = parts[0].strip(), parts[1].strip()
        if area == region:
            return level
    return None

def fetch_air_forecast(now):
    """에어코리아 대기오염예보 — PM10/PM25 등급을 날짜별로 반환.

    반환: {'YYYYMMDD': {'PM10': '보통', 'PM25': '좋음'}, ...}
    """
    result = {}
    if not DATA_GO_KR_KEY or not DATA_GO_KR_REGION:
        return result
    for code in ('PM10', 'PM25'):
        params = {
            'serviceKey': DATA_GO_KR_KEY,
            'returnType': 'json',
            'numOfRows': 10,
            'pageNo': 1,
            'searchDate': '',
            'informCode': code,
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
        for it in items:
            inform_date = it.get('informData', '').replace('-', '')  # 'YYYY-MM-DD' → 'YYYYMMDD'
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
    ULTRA_CAT_MAP = {'T1H': 'TMP', 'RN1': 'PCP', 'SKY': 'SKY', 'PTY': 'PTY', 'REH': 'REH', 'WSD': 'WSD'}
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

    cache = {'TMP': '15', 'SKY': '1', 'PTY': '0', 'REH': '50', 'WSD': '1.0', 'POP': '0'}
    for d_str in sorted(forecast_map.keys()):
        if d_str < today_str or d_str > short_end_str:
            continue
        day_data = forecast_map[d_str]
        tmps = [float(day_data[t]['TMP']) for t in day_data if 'TMP' in day_data[t]]
        if not tmps: continue
        t_min, t_max = int(min(tmps)), int(max(tmps))
        rep_t = '1200' if '1200' in day_data else sorted(day_data.keys())[0]
        rep_emoji, _ = get_weather_info(
            day_data[rep_t].get('SKY', cache['SKY']),
            day_data[rep_t].get('PTY', cache['PTY'])
        )
        desc = []
        has_future_data = False
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
                desc.append(f"[{t_str[:2]}시] {emoji} {wf_str} {cache['TMP']}°C ({' '.join(details)})")
                has_future_data = True
        if not has_future_data: continue
        # 미세먼지 정보 (있으면 summary/description에 추가)
        air_today = air_forecast.get(d_str, {})
        pm10_grade = air_today.get('PM10')
        pm25_grade = air_today.get('PM25')
        pm10_em = PM_GRADE_EMOJI.get(pm10_grade, '')
        pm25_em = PM_GRADE_EMOJI.get(pm25_grade, '')
        summary_suffix = ""
        if pm10_em or pm25_em:
            summary_suffix = f" {pm10_em}{pm25_em}"
            desc.insert(0, f"🌫️ 미세 {pm10_em} {pm10_grade or '-'} / 초미세 {pm25_em} {pm25_grade or '-'}\n")

        event = Event()
        event.add('dtstamp', now)
        event.add('summary', f"{rep_emoji} {t_min}°C/{t_max}°C{summary_suffix}")
        event.add('location', LOCATION_NAME)
        desc.append(f"\n최종 업데이트: {update_ts} (KST)")
        event.add('description', "\n".join(desc))
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

    print("최종 processed_dates:", sorted(processed_dates))
    print(f"기상특보 이벤트: {warning_count}건 추가")
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
