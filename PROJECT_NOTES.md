# 📓 프로젝트 작업 노트 (개발자용)

> 다음에 작업 재개 시 빠른 컨텍스트 복원을 위한 내부 문서.
> 일반 사용자 안내는 [README.md](README.md) 참고.

---

## 🏷 한 줄 요약

기상청 API + 공공데이터포털 API를 GitHub Actions로 매 3시간 폴링해서, 위경도·날씨·미세먼지·자외선·꽃가루·천문(일출/일몰/달/은하수)·지진/태풍 정보를 풍부하게 담은 `weather.ics` 를 생성하고 캘린더에 URL 구독으로 띄우는 프로젝트.

---

## 🎯 현재 상태 (2026-05-12 기준)

| 항목 | 상태 |
|------|------|
| 레포 | https://github.com/redchupa/weather-calendar (Public, fork 1개 생김) |
| GitHub Pages 가이드 | https://redchupa.github.io/weather-calendar/ (한/영 토글) |
| 자동 워크플로우 | ✅ 매 3시간 cron, 5회 연속 success |
| 시크릿 9개 | ✅ 모두 등록 (KMA + data.go.kr) |
| 캘린더 적용 | ✅ Google·Apple·Samsung 모두 동작 |

---

## ✨ 구현된 기능 (Tier별)

### Tier 0 — 기본 (단기/중기 예보)
- KMA `getVilageFcst` (D+0~3) + `getMidTa`/`getMidLandFcst` (D+4~10)
- 시간별 / 일별 ICS 이벤트 생성

### Tier 1 — 기상특보 + 자외선/꽃가루 (실측+예보)
- 기상특보 10종(`wrn_now_data_new.php`) → 별도 VEVENT, 카테고리 WEATHER_ALERT
- 미세먼지 PM10/PM2.5/O3 (에어코리아 실시간+예보)
- 자외선 (생활기상지수 V5)
- 꽃가루 참나무/소나무/잡초 (보건기상지수 V3)

### Tier 2 — 초단기예보 정밀도 + 지진/태풍
- 초단기예보(`getUltraSrtFcst`) — 0~6h 데이터를 단기예보에 머지
- 지진 (`eqk_list.php`) — 최근 7일, 규모 ≥ 3.0 만 캘린더에 추가
- 태풍 (`typ_now.php?mode=2`) — 활성 태풍 + 예측 진로 6개 시점

### Tier 3 — 천문 (오프라인 계산)
- 일출/일몰/시민박명/천문박명 (astral)
- 달 위상/조도/월출/월몰 (astral + ephem)
- 은하수 중심 고도 + 관측 가능 시간대 (ephem)

### Tier 4 — 친절한 자연어 표현
- 체감 메시지 (7단계, `temp_comfort_message`)
- 보퍼트 풍속 (12단계, `wind_message`)
- 16방위 풍향 (`wind_direction_text`)
- 우산 추천 (`umbrella_message`)
- 다음 비 예측 (`find_next_rain`)
- 어제 비교 (캐시 ICS에서 추출, `extract_yesterday_max`)

---

## 🌐 API 통합 현황 (7종)

| 출처 | 엔드포인트 | 용도 |
|------|----------|------|
| KMA apihub | `VilageFcstInfoService_2.0/getVilageFcst` | 단기예보 |
| KMA apihub | `VilageFcstInfoService_2.0/getUltraSrtFcst` | 초단기예보 |
| KMA apihub | `MidFcstInfoService/getMidTa` | 중기 기온 |
| KMA apihub | `MidFcstInfoService/getMidLandFcst` | 중기 육상 |
| KMA apihub | `wrn_now_data_new.php` | 기상특보 |
| KMA apihub | `eqk_list.php` | 지진 목록 |
| KMA apihub | `typ_now.php` | 태풍 정보+예측 |
| data.go.kr | `ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty` | 시도별 실시간 대기질 |
| data.go.kr | `ArpltnInforInqireSvc/getMinuDustFrcstDspth` | PM10/PM25 일별 예보 |
| data.go.kr | `LivingWthrIdxServiceV5/getUVIdxV5` | 자외선 |
| data.go.kr | `HealthWthrIdxServiceV3/get{Oak,Pine,Weeds}PollenRiskIdxV3` | 꽃가루 |

---

## 🔑 시크릿 (9개)

```
KMA_API_KEY          ← 기상청 API 허브 (apihub.kma.go.kr)
KMA_NX               ← 격자 X (예: 60)
KMA_NY               ← 격자 Y (예: 127)
REG_ID_TEMP          ← 중기기온 구역 (예: 11B10101)
REG_ID_LAND          ← 중기육상 구역 (예: 11B00000)
LOCATION_NAME        ← 표시 동네명 (예: 은계)
DATA_GO_KR_KEY       ← 공공데이터포털 일반 인증키
DATA_GO_KR_REGION    ← 에어코리아 19개 지역 중 하나 (예: 서울/경기남부)
LIVING_AREA_NO       ← 행정표준코드 10자리 (예: 4139000000 시흥)
```

내 시크릿: 시흥 기준 (`KMA_NX=60, KMA_NY=127, REG_ID_TEMP=11B20611, REG_ID_LAND=11B00000, DATA_GO_KR_REGION=경기남부, LIVING_AREA_NO=4139000000`)

---

## 🐛 정부 API 특이사항 (앞으로 비슷한 일 생기면 참고)

| 함정 | 해결 |
|------|------|
| **에어코리아 `searchDate` 빈 문자열** → stub 응답 (`informGrade` 누락) | 명시적 날짜(YYYY-MM-DD) 전달 |
| **에어코리아 `informCode` 대소문자** | `InformCode` (대문자 I) — 카멜케이스 |
| **자외선 endpoint 'V3.0'이라 표기되지만 실제 V5** | `LivingWthrIdxServiceV5/getUVIdxV5` (V3 아님) |
| **잡초 꽃가루 endpoint 정부측 오타** | `getWeedsPollenRiskndxV3` (Idx 아니라 ndx) |
| **강원 지역 응답명** | `영서`/`영동` (강원영서/강원영동 아님) — 코드에 alias 매핑 있음 |
| **지진 endpoint** | `eqk_list.php` (NOT `eqk_web.php`) |
| **태풍 endpoint** | `typ_now.php?mode=2` (NOT `typ_dpr_now.php`) |
| **활용신청 무반응** | 새로고침(F5) 후 다시 클릭 |
| **Google 캘린더 자체 캐시** | URL에 `?v=숫자` 캐시버스터 |

---

## 📁 코드 구조 (`update_calendar.py`, 1,438줄)

```
[1. 설정]                 환경변수 + 상수 (NX, NY, API 키, WRN_KEYWORDS 등)
[2. 헬퍼 함수]
  get_weather_info()      SKY/PTY → 이모지+한글
  get_mid_emoji()         중기 wf 텍스트 → 이모지
  fetch_api()             공통 API GET + 타입드 except
[3. 데이터 fetch]
  fetch_short()           단기예보
  fetch_ultra_short_forecast()  초단기예보
  fetch_air_realtime()    실시간 대기질
  fetch_air_forecast()    미세먼지 일별 예보
  fetch_uv_index()        자외선 V5
  fetch_pollen_risk()     꽃가루 V3 (참/소/잡 중 최대)
  fetch_warnings()        기상특보 (CSV 파싱)
  fetch_earthquakes()     지진 목록
  fetch_typhoons()        태풍 + 예측
[4. 자연어 표현]
  temp_comfort_message(), wind_message(), wind_direction_text(),
  umbrella_message(), find_next_rain(), extract_yesterday_max()
[5. 천문 (astral + ephem)]
  compute_moon_times(), compute_galactic_center_alt(),
  moon_phase_korean(), moon_phase_emoji(), format_time_kor()
[6. 좌표 변환]
  grid_to_latlon()        KMA 격자 → 위경도 (Lambert 역변환)
[7. main()]
  단기 fetch → 초단기 머지 → 미세먼지 fetch → 천문 계산 →
  for d_str in forecast_map:
    if d_str == today_str:
      → 풍부한 description (40줄+ 멀티섹션)
    else:
      → 간단 description (시간별 hourly)
  특보/지진/태풍 별도 VEVENT 추가
  weather.ics 작성 + 워크플로우 GITHUB_OUTPUT summary 전달
```

---

## 🔧 자주 쓰는 디버그 명령

```bash
# 최근 워크플로우 실행 상태
gh run list -R redchupa/weather-calendar --workflow=update.yml --limit 5

# 가장 최근 실행 로그에서 핵심 항목만 발췌
gh run view $(gh run list -R redchupa/weather-calendar --workflow=update.yml --limit 1 --json databaseId -q '.[0].databaseId') -R redchupa/weather-calendar --log 2>&1 | grep -E "자외선|꽃가루|미세먼지|지진|태풍|위경도|실시간|오늘 요약|WARN|Traceback"

# 수동 트리거
gh workflow run "Update Weather ICS" -R redchupa/weather-calendar

# 시크릿 목록 (값은 안 보임)
gh secret list -R redchupa/weather-calendar

# 가장 최근 ICS 헤더 + 오늘 이벤트 확인
git pull origin main
head -30 weather.ics
grep -A 60 "$(date +%Y%m%d)@short_summary" weather.ics
```

---

## 💡 향후 개선 아이디어 (Backlog)

### 우선순위 ★★★ (다음에 돌아오면 우선 고려)

- **지도/도시별 마이그레이션 가이드** — 시흥 외 사용자에게 `4139000000` 같은 코드를 본인 시군구로 바꾸는 절차를 더 명확히
- **워크플로우 알림** — 실패 시 Discord/Slack/이메일 알림 (현재는 GitHub UI에서만 확인)
- **Step 3 자동 계산기에 LIVING_AREA_NO 추가** — 현재는 NX/NY/REG_ID/AIR_REGION만 계산. lat/lon → 시군구 행정표준코드 매핑 추가 시 사용자가 코드 직접 검색 안 해도 됨

### 우선순위 ★★ (있으면 좋음)

- **호환 캘린더 앱 위젯/iOS 위젯** — 캘린더 앱 안 켜고 폰 홈 위젯에서 바로 보기
- **테스트 코드** — pytest 기반 단위 테스트 (시간 계산·매핑 로직 위주)
- **로컬 dry-run 모드** — CI 안 거치고 로컬에서 ICS 생성 검증 (env 파일 + `--dry-run` 플래그)
- **REG_ID_TEMP → LIVING_AREA_NO 정밀 매핑 테이블** — 시군구 250개 매핑 JSON 포함

### 우선순위 ★ (아이디어 차원)

- **다국어 ICS** — 영어 description 옵션 (현재 description은 한국어 고정)
- **추가 천문** — 행성 위치, 유성우 캘린더 추가
- **계절·기념일 통합** — 한국 공휴일 ICS 자동 병합 옵션
- **Apple Calendar 자체 캐시 회피 방안 (Mac CalDAV 직접 추가 옵션)**

### 우선순위 X (검토 후 보류)

- **HACS 통합 패키지화** — kr_component_kit처럼 HA용 통합 만들기 (별도 프로젝트로 더 적합)
- **Discord 봇** — 매일 아침 날씨 요약 메시지 (스코프 벗어남)

---

## 🚦 작업 재개 체크리스트

다음에 돌아왔을 때:

1. **첫 5분: 상태 확인**
   - [ ] 워크플로우 최근 실행 success인가? (`gh run list ...`)
   - [ ] `weather.ics` 가 최근에 갱신됐나? (`git log -1 weather.ics`)
   - [ ] 사용자가 보고한 문제가 KMA/data.go.kr API 변경 때문인지 확인 (응답 구조 dump)

2. **이슈 진단 시**
   - [ ] `update_calendar.py` 의 `fetch_*` 함수 한 군데에 `print(f"[DIAG] ...")` 임시 추가
   - [ ] 한 번 manual trigger 후 로그 확인
   - [ ] 원인 파악 후 fix → 진단 로그 제거 → 커밋

3. **기능 추가 시**
   - [ ] 새 API라면 활용신청 안내를 README + docs/index.html Step 2 양쪽에 추가
   - [ ] 새 시크릿이 필요하면 `update.yml` env 매핑 + 9→10개 카운트 업데이트
   - [ ] 새 description 정보는 오늘 이벤트(rich description)에만 추가 (D+1~ 는 간결 유지)

4. **푸시 전**
   - [ ] `python -c "import ast; ast.parse(open('update_calendar.py', encoding='utf-8').read())"`
   - [ ] README.md 와 README.en.md 동일 정보 유지
   - [ ] docs/index.html 변경 시 KO/EN 양쪽 `data-lang` 페어 유지

---

## 📜 주요 마일스톤 (커밋 히스토리 요약)

| 마일스톤 | 결과 |
|---------|------|
| 초기 fork → 독립 레포 전환 | redchupa/weather-calendar 신규 생성, fork 삭제 |
| RFC 5545 ICS 표준 fix | VERSION/PRODID/DTSTAMP 추가 → Google 캘린더 호환성 해결 |
| 워크플로우 현대화 | Python 3.9→3.12, cron 활성, requirements.txt, retry-on-conflict push |
| Tier 1+2+3 풍부화 | 미세먼지/자외선/꽃가루/특보/지진/태풍/천문 모두 통합 (오늘 description 40줄+) |
| 한/영 국제화 | README.en.md + docs/index.html 언어 토글 (localStorage 저장) |
| 모바일 반응형 + UX 마감 | sponsor flex grid, 히어로 이미지, 시군구 코드 표 |

---

## 🔗 관련 외부 자원

- KMA API 허브: https://apihub.kma.go.kr/
- 공공데이터포털: https://www.data.go.kr/
- 공공데이터포털 마이페이지 인증키: https://www.data.go.kr/iim/api/selectAcountList.do
- 법정동코드 검색: https://www.code.go.kr/stdcode/regCodeL.do
- 에어코리아 (참고): https://www.airkorea.or.kr/
- 행정안전부 행정표준코드: https://www.code.go.kr/

---

**마지막 작업일**: 2026-05-12
**작업 세션 종료 시점 상태**: 운영 안정. 다음 큰 작업 없으면 자동 운영만으로 충분.
