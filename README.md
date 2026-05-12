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

## 🚀 설치 & 사용

자세한 설치 가이드는 [**📖 설정 가이드 페이지**](https://redchupa.github.io/weather-calendar/) 를 참고하세요.

요약:

1. 이 레포지토리를 본인 계정으로 **Fork** 합니다.
2. [기상청 API 허브](https://apihub.kma.go.kr/) 가입 후 인증키를 발급받고, 아래 세 서비스에 **활용 신청**을 합니다.
   - 단기예보 〉 4.3 단기예보조회
   - 중기예보 〉 2.2 중기기온조회
   - 중기예보 〉 2.3 중기육상예보조회
3. Fork한 레포의 `Settings → Secrets and variables → Actions` 에서 아래 6개 시크릿을 등록합니다.

   | 시크릿 이름 | 설명 |
   |---|---|
   | `KMA_API_KEY` | 기상청 API 허브 인증키 |
   | `KMA_NX` | 단기예보 격자 X 좌표 (예: `60`) |
   | `KMA_NY` | 단기예보 격자 Y 좌표 (예: `127`) |
   | `REG_ID_TEMP` | 중기기온 구역 코드 (예: `11B10101`) |
   | `REG_ID_LAND` | 중기육상 구역 코드 (예: `11B00000`) |
   | `LOCATION_NAME` | 캘린더 이벤트의 `LOCATION` 에 표시될 동네 이름 |

4. `Actions` 탭에서 워크플로우를 **활성화** 한 뒤, `Update Weather ICS` 워크플로우를 수동 실행(`Run workflow`)합니다.
5. 생성된 `weather.ics` 의 **Raw URL** 을 캘린더 앱에 URL 구독으로 등록합니다.

## ⏰ 자동 갱신 활성화

기본적으로 `.github/workflows/update.yml` 의 `schedule:` 트리거는 **주석 처리**되어 있어, 워크플로우는 수동 실행(`workflow_dispatch`) 이나 `push` 시에만 동작합니다.

자동 갱신을 원하면 [.github/workflows/update.yml](.github/workflows/update.yml) 에서 다음 부분의 `#` 을 제거하세요.

```yaml
on:
  schedule:
    - cron: '15 17,20,23,2,5,8,11,14 * * *'   # KST 기준 매 3시간
```

> ⚠️ 단, 구독한 캘린더 앱(Google/Apple/Samsung)은 ICS URL을 **자체 캐시 주기(보통 8~24시간)** 에 따라 갱신합니다. 소스가 매 3시간 업데이트되어도, 클라이언트 반영은 그보다 느릴 수 있습니다.

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

원본 [Murianwind/weather-calendar](https://github.com/Murianwind/weather-calendar) 에 명시된 라이선스가 없으므로, 본 레포 역시 별도 라이선스를 두지 않습니다. 사용 시 원작자 표기를 유지해 주세요.
