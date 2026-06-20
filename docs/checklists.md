# 자체 체크리스트

## SVG 입력 체크리스트

- 원본 SVG를 직접 수정하지 않는다.
- `rect`, `polygon`, `polyline`, `line`, `circle`, `ellipse`, `path`, `text`를 누락 없이 보존한다.
- class 기반 CSS와 transform은 geometry 추론에 반영한다.
- 너무 많은 선은 병합/그룹화 통계로 정리하되, 원본 vector node id는 보존한다.

## 라벨 체크리스트

- `text + tspan`을 병합한다.
- typographic quote를 ASCII quote로 정규화한다.
- `LIVING ROOM24'4" x 18'0"` 같은 라벨을 방 이름과 치수 텍스트로 분리한다.
- `LOGO HERE`, 면적 정보, 고지문은 공간 entity로 승격하지 않는다.
- `FP`, `DW` 같은 축약 라벨은 fixture 후보로 분리한다.

## Entity 체크리스트

- Space, Wall, Door, Window, Fixture, Annotation을 생성한다.
- 벽은 긴 선분, 두꺼운 boundary polygon, 공간 외곽 edge 후보를 함께 본다.
- 창문은 얇은 반복 line/polygon 패턴과 벽 정렬성을 본다.
- 문은 swing arc, leaf, hinge 후보를 함께 본다.
- 애매한 문 방향은 확정하지 않고 `unknown` 또는 검토 필요로 남긴다.

## 관계 체크리스트

- 공간과 라벨의 anchor 포함 관계를 우선한다.
- 실패 시 nearest 후보로 연결하되 confidence를 낮추고 검토 대상으로 남긴다.
- `contains`, `locatedIn`, `boundedBy`, `locatedOn`, `connects`, `opensInto` 관계를 생성한다.

## 공사 제안 체크리스트

- 출입구와 주요 이동 동선을 막지 않는다.
- 새 공간은 문이나 개구부로 접근 가능해야 한다.
- 창문, 채광, 통풍 가능성을 함께 기록한다.
- 기존 팬트리/수납/설비 변경은 구조와 설비 검토 필요로 표시한다.
- 공사 제안은 확정 설계가 아니라 검토용 proposal로 표기한다.

## 동선/바람 체크리스트

- 이동 화살표는 문 또는 개구부 waypoint를 통과해야 한다.
- 주 동선과 보조 동선을 구분한다.
- 바람 흐름은 한 방만 보지 않고 전체 층의 가능한 연결을 본다.
- airflow는 qualitative graph proxy이며 CFD 결과라고 말하지 않는다.
- 창문 개폐 가능성, 주 풍향, 개구부 면적, 천장고는 unknown으로 남긴다.

## HTML/시각 검증 체크리스트

- HTML은 한국어로 표시한다.
- Boolean은 `예/아니요`처럼 사람이 읽는 표현으로 표시한다.
- 내부 위험도 태그는 자연어 문장으로 풀어쓴다.
- HTML은 외부 서버 없이 브라우저에서 열려야 한다.
- HTML은 SVG를 `<svg>...</svg>`로 직접 포함해야 한다.
- `<img>`, `<object>`, `<embed>`, `<iframe>` 방식으로 SVG를 참조하지 않는다.

## 공개 repo 체크리스트

- README 첫 화면에 사용 가치와 예시 이미지가 보인다.
- 설치 방법은 Codex skill 기준으로 짧게 제공한다.
- 샘플 도면, 3개 공사 요청, 체크리스트를 한 자리에서 볼 수 있다.
- 구조/법규/설비/인허가 판단이 아니라는 한계를 명확히 쓴다.
- 공개 가능한 샘플만 포함한다.
