# Claude Code 안내

이 폴더에서 작업 재개 시 **반드시 [PROJECT_NOTES.md](PROJECT_NOTES.md) 를 먼저 읽고** 컨텍스트를 복원하세요.

## 빠른 컨텍스트

- **프로젝트**: KMA + data.go.kr API 통합 → 풍부한 ICS 캘린더 생성
- **레포**: https://github.com/redchupa/weather-calendar
- **메인 스크립트**: [update_calendar.py](update_calendar.py) (1,438줄)
- **상태**: 운영 안정. 매 3시간 cron 자동 실행 중.
- **마지막 작업일**: 2026-05-12

## 작업 재개 시 표준 절차

1. [PROJECT_NOTES.md](PROJECT_NOTES.md) 읽기 (전체 컨텍스트)
2. 사용자가 보고한 이슈가 있다면 `gh run list -R redchupa/weather-calendar` 로 최근 워크플로우 상태 확인
3. 정부 API 특이사항(V5 endpoint, Riskndx 오타, searchDate stub 등)은 PROJECT_NOTES.md 의 "🐛 정부 API 특이사항" 표 참고
4. 푸시 전 체크리스트는 PROJECT_NOTES.md 의 "🚦 작업 재개 체크리스트" 참고

## 사용자 환경 메모

- 사용자 시크릿 (시흥 기준): `KMA_NX=60, KMA_NY=127, REG_ID_LAND=11B00000, DATA_GO_KR_REGION=경기남부, LIVING_AREA_NO=4139000000`
- 한국어 응답 선호. 짜친 멘트 싫어함.
- 모바일에서도 가이드 페이지가 예쁘게 보이길 원함.
- README/가이드 페이지 둘 다 한/영 지원 유지 필요.
