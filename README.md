# ☀️ 기상청 날씨 캘린더 (Weather Calendar)

[![Update Weather ICS](https://github.com/redchupa/weather-calendar/actions/workflows/update.yml/badge.svg)](https://github.com/redchupa/weather-calendar/actions/workflows/update.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Pages](https://img.shields.io/badge/Setup_Guide-GitHub_Pages-2563eb?logo=github)](https://redchupa.github.io/weather-calendar/)

> **🌟 5분만에 세팅하고, 내 폰 캘린더에 매일 한국 날씨를 자동으로 표시하기**

기상청 API를 이용해 **오늘부터 10일치 한국 날씨 예보**를 iCalendar(`.ics`) 파일로 자동 생성하고, GitHub Actions로 주기적으로 갱신해 Google / Apple / Samsung 캘린더에 **URL 구독** 으로 띄우는 프로젝트입니다. 위젯 설치도 추가 앱 설치도 필요 없어요. 그냥 평소 쓰던 캘린더 앱에 한 줄 추가만 하면 끝.

<p align="center">
  <img src="docs/preview-mobile.png" alt="모바일 캘린더 적용 예시" width="320">
  <br>
  <em>📱 실제 갤럭시/Google 캘린더 앱 적용 모습 — 매일 날짜 칸에 날씨 이모지 + 최저/최고 기온</em>
</p>

## ✨ 특징

- 🌤️ **단기 D+0~3** 시간별 상세 / **중기 D+4~10** 일별 요약, 총 11일치 예보
- ⚡ **초단기예보(0~6시간)** 자동 병합 — 가까운 시간 정확도 향상
- 🚨 **기상특보 자동 연동** — 폭염·호우·한파 등 10종 경보를 별도 일정으로 표시
- 🌫️ **미세먼지/초미세먼지** 등급 표시 (선택, 공공데이터포털 키 필요)
- 📱 Google·Apple·Samsung·Naver 등 **표준 ICS 구독을 지원하는 모든 캘린더 앱** 호환
- 🏠 한국 **어느 동네든** 격자좌표(NX/NY) + 구역코드만 알면 OK (가이드 페이지에 자동 계산기 내장)
- 🆓 모든 API 무료 + GitHub Free 플랜으로 **완전 무료** 운영
- 🎨 이모지로 한눈에 — ☀️맑음 / ⛅구름많음 / ☁️흐림 / 🌧️비 / ❄️눈 / ☔소나기 / 🟢🟡🟠🔴 (대기질)

---

## 📅 ICS 내부 데이터 예시

이벤트 제목(SUMMARY) 예시: `⛅ 14°C/24°C`
이벤트 본문(DESCRIPTION) 예시:
```
[09시] ☁️ 흐림 18°C (💧85% 🚩1.4m/s)
[10시] ☁️ 흐림 19°C (💧80% 🚩1.3m/s)
…
최종 업데이트: 2026-05-12 08:59:38 (KST)
```

- **D+0 ~ D+3 (단기 예보)**: 시간별 상세 (기온/하늘/강수형태/강수확률/습도/풍속)
- **D+4 ~ D+10 (중기 예보)**: 오전/오후 또는 종일 요약 + 강수확률 + 최저/최고 기온

---

## 🗺️ 전체 흐름 한눈에 보기

```
[기상청 API] ──fetch──> [GitHub Actions: update_calendar.py]
                                  │
                                  ▼
                          [weather.ics 생성]
                                  │
                          ──── commit/push ───→ GitHub 저장소
                                                     │
                                            Raw URL  │
                                                     ▼
                                  [내 스마트폰 캘린더 앱이 URL 구독]
```

처음 한 번만 세팅해 두면, 그 다음부터는 **워크플로우가 ICS를 갱신 → 캘린더 앱이 알아서 동기화** 하는 구조라서 손이 안 가요.

---

## 🚀 처음부터 따라하는 설치 가이드

> 💡 더 친절한 시각 가이드(좌표 자동 계산기 포함)는 **[📖 GitHub Pages 가이드](https://redchupa.github.io/weather-calendar/)** 를 참고하세요.

### 1️⃣ 이 레포를 본인 계정으로 Fork

1. 이 페이지 우측 상단 **[Fork]** 버튼 클릭
2. "Create fork" 누르면 본인 계정에 복사본이 생김
3. 이후 단계는 모두 **본인 계정의 Fork된 레포에서** 진행 (원본이 아님)

### 2️⃣ 기상청 API 허브에서 인증키 발급

1. [기상청 API 허브](https://apihub.kma.go.kr/) 가입 (이메일 + 휴대폰 본인인증만 있으면 됨, 공동인증서 불필요)
2. 좌측 메뉴 **[예특보]** → 아래 서비스들에 각각 "활용 신청" 클릭
   - **단기예보** › `4.2 초단기예보조회` (정확도 향상용)
   - **단기예보** › `4.3 단기예보조회`
   - **중기예보** › `2.2 중기기온조회`
   - **중기예보** › `2.3 중기육상예보조회`
   - **기상특보** › `2. 특보현황 조회` (특보 이벤트용, `wrn_now_data_new.php`)
3. 상단 **[마이페이지] → [인증키 현황]** 에서 **API Key 값을 복사** (한 줄 긴 문자열)

> ℹ️ 활용 신청은 보통 즉시 승인되지만, 가끔 몇 분 걸릴 수 있어요.

### 3️⃣ 내 동네의 NX/NY 좌표 + 구역 코드 찾기

기상청은 동네 좌표를 격자(NX, NY)로, 중기예보 구역을 별도 코드(11B10101 식)로 관리해요.

가장 쉬운 방법은 **[📖 GitHub Pages 가이드](https://redchupa.github.io/weather-calendar/)** 의 **3단계 자동 계산기**:
- 가까운 예보 지점을 드롭다운에서 고르고
- 도로명 주소를 입력하면
- **NX, NY, REG_ID_TEMP, REG_ID_LAND** 네 값이 한 번에 계산돼요

이 네 값을 메모해두세요.

### 4️⃣ GitHub Secrets에 값 등록 (총 6개)

본인 Fork 레포에서:
- **Settings** 탭 클릭
- 왼쪽 메뉴 **Secrets and variables → Actions** 클릭
- 초록색 **[New repository secret]** 버튼 클릭
- 아래 6개를 **하나씩** 등록 (Name과 Secret 값 모두 입력 후 "Add secret")

**필수 시크릿 (8개)**

| Name | 값 (Secret) | 어디서 얻나 |
|---|---|---|
| `KMA_API_KEY` | 기상청 인증키 | 2단계에서 복사한 값 |
| `KMA_NX` | 단기예보 격자 X (예: `60`) | 3단계 결과 |
| `KMA_NY` | 단기예보 격자 Y (예: `127`) | 3단계 결과 |
| `REG_ID_TEMP` | 중기기온 구역 코드 (예: `11B10101`) | 3단계 결과 |
| `REG_ID_LAND` | 중기육상 구역 코드 (예: `11B00000`) | 3단계 결과 |
| `LOCATION_NAME` | 캘린더 일정에 표시될 동네 이름 (예: `우리집`) | 직접 정함 |
| `DATA_GO_KR_KEY` | 공공데이터포털 일반 인증키 (🌫️ 미세먼지용) | [공공데이터포털](https://www.data.go.kr/) → [에어코리아 대기오염정보](https://www.data.go.kr/data/15073861/openapi.do) 활용신청 |
| `AIR_REGION` | 미세먼지 예보 지역명 | 아래 19개 중 하나 |

> ⚠️ 시크릿 이름은 **대소문자/오타 주의**. 한 글자라도 다르면 워크플로우가 빈 값을 받아 실패해요.
>
> 💡 **`AIR_REGION` 가능 값 (에어코리아 표기 그대로)**: `서울`, `부산`, `대구`, `인천`, `광주`, `대전`, `울산`, `세종`, `경기북부`, `경기남부`, `강원영서`, `강원영동`, `충북`, `충남`, `전북`, `전남`, `경북`, `경남`, `제주`

> ⚠️ 시크릿 이름은 **대소문자/오타 주의**. 한 글자라도 다르면 워크플로우가 빈 값을 받아 실패해요.
>
> 💡 **`DATA_GO_KR_KEY` 발급법**: [공공데이터포털](https://www.data.go.kr/) 가입 → [한국환경공단_에어코리아_대기오염정보](https://www.data.go.kr/data/15073861/openapi.do) 활용신청 → 1~2일 후 승인되면 마이페이지에서 일반 인증키 복사. 이 키 하나로 공공데이터포털의 다양한 API에 공통으로 사용 가능.

### 5️⃣ 워크플로우 활성화 & 첫 실행

1. **[Actions]** 탭 클릭
2. (Fork 직후라면) 큰 안내 박스의 **"I understand my workflows, go ahead and enable them"** 버튼 클릭 (최초 1회만)
3. 왼쪽 워크플로우 목록에서 **`Update Weather ICS`** 선택
4. 우측의 **[Run workflow]** 드롭다운 → 초록색 **[Run workflow]** 버튼 클릭
5. 30초~1분 정도 기다리면 ✅ 초록 체크 마크가 표시되면서 완료
6. 레포 루트의 **`weather.ics`** 파일이 새 데이터로 업데이트되어 있을 거예요

> ❌ 만약 ❌ 빨간 X가 뜬다면 → 거의 100% 시크릿 등록 누락/오타. 4단계로 돌아가서 6개 모두 정확히 등록됐는지 확인하세요. (FAQ 참고)

### 6️⃣ 내 캘린더 앱에 등록하기

**(a) ICS의 Raw URL 복사**
1. 본인 레포의 **`weather.ics`** 파일 클릭
2. 우측 상단 **[Raw]** 버튼 클릭
3. 주소창 URL 복사
   - 형식: `https://raw.githubusercontent.com/<본인아이디>/weather-calendar/main/weather.ics`

**(b) Google 캘린더 (PC 웹 기준 — 가장 추천)**
1. [calendar.google.com](https://calendar.google.com) 접속
2. 왼쪽 **"다른 캘린더"** 옆 **`+`** 버튼 클릭
3. **"URL로 만들기"** 선택
4. 위 Raw URL 붙여넣기 → **[캘린더 추가]**

> 📱 안드로이드(삼성 갤럭시 포함): Samsung 캘린더가 ICS URL 구독을 직접 지원하지 않으니, **PC에서 Google 캘린더에 위 방식으로 추가** → 폰의 Google 캘린더 앱과 자동 동기화하는 게 가장 깔끔합니다.

**(c) iPhone / Mac (Apple 캘린더)**
1. iPhone: **설정 → 캘린더 → 계정 → 계정 추가 → 기타 → 구독 캘린더 추가**
2. 서버 칸에 Raw URL 붙여넣기 → 다음 → 저장

### 7️⃣ 📱 모바일 앱에서 보이지 않을 때 (꼭 확인)

> PC 웹 Google 캘린더에선 잘 보이는데 **폰 앱에선 안 보이는 경우가 매우 흔합니다**. Google이 URL로 추가한 캘린더를 기본적으로 모바일 동기화 목록에 넣지 않기 때문이에요.
>
> ❗ 중요: 아래 **A → B → C 세 단계를 순서대로** 마쳐야 폰에 보입니다. A만 해두고 기다리면 자동 반영 안 돼요.

#### A. Google "Sync Select" 페이지에서 체크 (PC/브라우저)

1. 브라우저로 접속: **https://calendar.google.com/calendar/syncselect**
2. 본인 Google 계정 로그인 상태에서, 추가한 캘린더(예: `기상청 날씨`) 체크박스 **ON**
3. **[Save]** 클릭

> 이 페이지는 모바일 동기화의 **마스터 스위치**입니다. 여기서 체크돼 있지 않으면 아래 B/C 단계도 의미가 없어요.

#### B. 모바일 Google 캘린더 앱에서 "동기화" 켜기

A를 마쳤다고 자동으로 폰에 뜨지 않습니다. 앱에 들어가서 **수동으로 동기화를 켜줘야** 캘린더 목록에 나타나요.

1. 폰에서 Google 캘린더 앱 열기
2. 좌측 상단 **☰ 메뉴** → **설정**
3. 본인 Google 계정 아래에서 **`기상청 날씨`** 캘린더 항목 탭
4. **"동기화" 토글 ON**
5. 뒤로 돌아오기

> 캘린더 이름이 설정 목록에 아예 안 보이면 → A를 안 했거나 저장이 안 된 거예요. 1단계로 돌아가세요.

#### C. 모바일 앱에서 "표시"(체크박스) 활성화

동기화를 켜도 캘린더 목록에 회색 체크박스로 있을 수 있어요. **체크해야 실제 화면에 표시**됩니다.

1. 좌측 ☰ 메뉴 다시 열기
2. 캘린더 목록에서 **`기상청 날씨`** 좌측 체크박스를 탭해 **색이 채워진 상태**로 만들기
3. 메뉴 닫고 월/주 뷰에서 날씨가 보이는지 확인

여기까지 하면 폰에 날씨 캘린더가 정상 표시됩니다. 🎉

#### 다른 환경에서는?

| 환경 | 방법 |
|---|---|
| **삼성 갤럭시 — Samsung 캘린더 앱** | ⚠️ 삼성 캘린더는 구독 캘린더를 표시하지 못 합니다. **Google 캘린더 앱을 설치해서** 위 A→B→C 진행하세요. |
| **iPhone — 권장(가장 안정적)** | 구글 거치지 말고 Apple 캘린더에 **직접 구독**: 설정 → 캘린더 → 계정 → 계정 추가 → 기타 → 구독 캘린더 추가 → 서버에 Raw URL |
| **iPhone — Google 경유** | iOS용 Google 캘린더 앱 설치 후 위 A→B→C 진행. iPhone 기본 캘린더 앱에는 안 보입니다 (CalDAV가 구독 캘린더 미동기화) |

#### 그래도 안 보일 때 점검 순서

| 순서 | 확인할 것 |
|---|---|
| 1 | PC 웹 Google 캘린더에서 보이는가? → 안 보이면 구독 자체 문제 |
| 2 | https://calendar.google.com/calendar/syncselect 에서 체크 ON 되어 있나? (A) |
| 3 | 모바일 앱 설정 → 해당 캘린더 → "동기화" 토글 ON? (B) |
| 4 | 좌측 메뉴 캘린더 목록 체크박스가 채워져 있나? (C) |
| 5 | 모바일 앱 완전 종료 후 재실행 |
| 6 | 최대 24시간 기다림. 그래도 안 되면 캘린더 삭제 → 재구독 |

---

## ❓ 자주 묻는 질문 (FAQ)

<details>
<summary><b>Q. 첫 실행이 빨간 X(실패)로 끝났어요</b></summary>

99% 시크릿 등록 문제입니다. 다음을 확인하세요:
- 시크릿 6개 **모두** 등록됐는지 (`Settings → Secrets and variables → Actions`)
- **이름 철자/대소문자**가 정확한지 (예: `KMA_API_KEY` ≠ `kma_api_key`)
- `KMA_API_KEY` 값에 공백/줄바꿈이 안 섞였는지

수정 후 Actions 탭에서 다시 **Run workflow** 를 누르면 됩니다.
</details>

<details>
<summary><b>Q. 캘린더에 등록했는데 날씨가 안 보여요</b></summary>

체크리스트:
1. 워크플로우가 실제로 성공했는지 — Actions 탭에서 초록 체크 확인
2. 본인 레포의 `weather.ics` 파일에 데이터가 들어있는지 확인
3. **PC 웹에선 보이는데 폰에선 안 보이는 경우 → [7️⃣ 모바일 앱에서 보이지 않을 때](#7%EF%B8%8F%E2%83%A3--모바일-앱에서-보이지-않을-때-꼭-확인) 섹션 참고** (Google Sync Select 누락이 가장 흔한 원인)
4. 캘린더 앱 동기화 주기 — Google 캘린더는 URL 구독을 **8~24시간 간격**으로 갱신합니다
</details>

<details>
<summary><b>Q. "Node.js 20 is deprecated" 경고가 떠요</b></summary>

**무시해도 됩니다.** 워크플로우 안에 `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` 설정이 있어서 GitHub이 "이 액션들은 Node 20용인데 Node 24로 강제 실행했다"고 알려주는 단순 경고입니다. 결과는 정상 성공이에요.
</details>

<details>
<summary><b>Q. 캘린더 추가할 때 "캘린더 공개하기" 옵션이 뭐예요?</b></summary>

이건 **Google 캘린더 안의 내 사본**을 외부에 공개할지를 묻는 옵션이지, GitHub의 ICS 소스 공개 여부와는 별개입니다. **개인이 본인 폰에서 날씨를 보려는 용도라면 끄세요(기본값).** 가족/팀과 공유하거나 블로그에 임베드할 때만 켜면 됩니다.
</details>

<details>
<summary><b>Q. 데이터는 얼마나 자주 갱신되나요?</b></summary>

- **기상청 원본**: 단기는 매 3시간, 중기는 하루 2회 (06시/18시)
- **이 레포의 weather.ics**: 기본은 수동 실행 / push 시. 자동 갱신을 원하면 아래 "자동 갱신 활성화" 섹션을 참고해 cron 주석을 해제하세요
- **캘린더 앱 반영**: Google/Apple 모두 8~24시간 캐시 사용 (이 부분만은 사용자가 제어 불가)
</details>

---

## ⏰ 자동 갱신

기본적으로 [.github/workflows/update.yml](.github/workflows/update.yml) 의 `schedule:` 이 **활성화**되어 있어 워크플로우는 다음 시점에 자동으로 실행됩니다 (KST 기준):

| 시각 | 02:15 | 05:15 | 08:15 | 11:15 | 14:15 | 17:15 | 20:15 | 23:15 |
|---|---|---|---|---|---|---|---|---|

기상청 단기예보 발표 시각(매 3시간) 직후를 노린 스케줄입니다. 자동 갱신이 필요 없으면 워크플로우 파일의 `schedule:` 블록을 주석 처리하면 됩니다.

> ⚠️ 단, 구독한 캘린더 앱은 ICS URL을 **자체 캐시 주기(보통 8~24시간)** 에 따라 갱신합니다. 소스가 매 3시간 업데이트돼도, 클라이언트 반영은 그보다 느릴 수 있어요.

---

## 🛠 기술 스택

- **Python 3.12** — `requests`, `pytz`, `icalendar` (의존성은 [requirements.txt](requirements.txt))
- **GitHub Actions** — cron(매 3시간) / `repository_dispatch` / `workflow_dispatch` 트리거
- **기상청 API 허브** — `VilageFcstInfoService_2.0`, `MidFcstInfoService`

## 📂 파일 구조

```
.
├── update_calendar.py        # KMA API → ICS 생성 스크립트
├── requirements.txt          # Python 의존성 명세
├── weather.ics               # 생성된 캘린더 파일 (Raw URL 구독 대상)
├── .github/workflows/
│   └── update.yml            # 워크플로우 정의
├── .gitignore
├── LICENSE
└── docs/                     # GitHub Pages 설정 가이드
    ├── index.html
    ├── region_codes.json
    └── calendar.png
```

## 📜 라이선스

[MIT License](LICENSE) © 2026 redchupa

---

> **🙏 출처(Original Author)**
> 이 프로젝트는 [**@Murianwind**](https://github.com/Murianwind) 님의 [Murianwind/weather-calendar](https://github.com/Murianwind/weather-calendar) 를 기반으로 제작되었습니다. 원작자께 감사드립니다.
