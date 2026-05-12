# ☀️ 기상청 날씨 캘린더 (Weather Calendar)

기상청 API(`apihub.kma.go.kr`)를 이용해 **오늘부터 10일치 한국 날씨 예보**를 iCalendar(`.ics`) 파일로 자동 생성하고, GitHub Actions로 주기적으로 갱신하는 프로젝트입니다.

생성된 `weather.ics` 파일의 **Raw URL** 을 Google / Apple / Samsung 캘린더 등에 **URL 구독**으로 등록하면, 매일 날짜 칸에 날씨 아이콘과 최저/최고 기온이 표시됩니다.

> **🙏 출처(Original Author)**
> 이 프로젝트는 [**@Murianwind**](https://github.com/Murianwind) 님의 [Murianwind/weather-calendar](https://github.com/Murianwind/weather-calendar) 를 기반으로 제작되었습니다. 원작자께 감사드립니다.

---

## 📅 결과 예시

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

1. [기상청 API 허브](https://apihub.kma.go.kr/) 가입 (정부24/공동인증서 필요)
2. 좌측 메뉴 **[예특보]** → 아래 **세 가지 서비스에 각각 "활용 신청"** 클릭
   - **단기예보** › `4.3 단기예보조회`
   - **중기예보** › `2.2 중기기온조회`
   - **중기예보** › `2.3 중기육상예보조회`
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

| Name | 값 (Secret) | 어디서 얻나 |
|---|---|---|
| `KMA_API_KEY` | 기상청 인증키 | 2단계에서 복사한 값 |
| `KMA_NX` | 단기예보 격자 X (예: `60`) | 3단계 결과 |
| `KMA_NY` | 단기예보 격자 Y (예: `127`) | 3단계 결과 |
| `REG_ID_TEMP` | 중기기온 구역 코드 (예: `11B10101`) | 3단계 결과 |
| `REG_ID_LAND` | 중기육상 구역 코드 (예: `11B00000`) | 3단계 결과 |
| `LOCATION_NAME` | 캘린더 일정에 표시될 동네 이름 (예: `우리집`) | 직접 정함 |

> ⚠️ 시크릿 이름은 **대소문자/오타 주의**. 한 글자라도 다르면 워크플로우가 빈 값을 받아 실패해요.

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
3. 캘린더 앱 동기화 주기 — Google 캘린더는 URL 구독을 **8~24시간 간격**으로 갱신합니다. 처음 등록 직후엔 곧 보이지만, 갱신은 즉시가 아닐 수 있어요
4. ICS의 표준 호환성 — 이 코드는 `VERSION` / `PRODID` / `DTSTAMP` 같은 RFC 5545 필수 필드가 빠져 있어서 일부 캘린더에서 안 보일 수 있습니다 (개선 예정)
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

## ⏰ 자동 갱신 활성화 (선택)

기본적으로 [.github/workflows/update.yml](.github/workflows/update.yml) 의 `schedule:` 트리거는 **주석 처리**되어 있어, 워크플로우는 수동 실행(`workflow_dispatch`) 이나 `push` 시에만 동작합니다.

매 3시간 자동 갱신을 원하면 다음 두 줄의 `#` 을 제거하고 커밋하세요:

```yaml
on:
  schedule:
    - cron: '15 17,20,23,2,5,8,11,14 * * *'   # KST 기준 매 3시간 (UTC 변환됨)
```

> ⚠️ 단, 구독한 캘린더 앱은 ICS URL을 **자체 캐시 주기(보통 8~24시간)** 에 따라 갱신합니다. 소스가 매 3시간 업데이트돼도, 클라이언트 반영은 그보다 느릴 수 있어요.

---

## 🛠 기술 스택

- **Python 3.9** — `requests`, `pytz`, `icalendar`
- **GitHub Actions** — 스케줄 또는 `repository_dispatch` 로 트리거
- **기상청 API 허브** — `VilageFcstInfoService_2.0`, `MidFcstInfoService`

## 📂 파일 구조

```
.
├── update_calendar.py        # KMA API → ICS 생성 스크립트
├── weather.ics               # 생성된 캘린더 파일 (Raw URL 구독 대상)
├── .github/workflows/
│   └── update.yml            # 워크플로우 정의
└── docs/                     # GitHub Pages 설정 가이드
    ├── index.html
    ├── region_codes.json
    └── calendar.png
```

## 📜 라이선스

[MIT License](LICENSE) © 2026 redchupa

원본 아이디어 및 초기 코드의 출처는 [@Murianwind](https://github.com/Murianwind) 님의 [Murianwind/weather-calendar](https://github.com/Murianwind/weather-calendar) 입니다.
