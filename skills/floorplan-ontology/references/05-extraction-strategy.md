# 추출 전략

## 기본 전략

이 SVG는 의미 있는 레이어 구조나 id를 제공하지 않는다. 따라서 다음 단서를 조합한다.

- 텍스트 라벨
- 도형 종류
- 도형 스타일
- 위치와 크기
- 도형 간 포함 관계
- 도형 간 접촉 관계
- 반복 패턴
- 문과 창문에 특화된 기하 형태

## 라벨 추출

### 라벨 병합

`text` 내부의 `tspan`을 모두 순서대로 읽어 하나의 raw label로 만든다.

예:

```text
LIVING ROOM24'4" x 18'0"
```

### 이름과 치수 분리

방 라벨은 보통 이름과 치수가 붙어 있다.

규칙:

- 치수 패턴: `number ' number " x number ' number "`
- 치수 앞쪽은 공간 이름 후보
- 치수만 있으면 dimension annotation
- 약어는 fixture나 appliance 후보

예:

```json
{
  "rawText": "KITCHEN24'4\" x 10'8\"",
  "name": "KITCHEN",
  "dimensionText": "24'4\" x 10'8\"",
  "labelType": "room_label"
}
```

### 라벨 카테고리

초기 대상 SVG에서 관찰되는 라벨:

- `PANTRY`
- `VERANDA`
- `LIVING ROOM`
- `OFFICE`
- `ENTRY`
- `BEDROOM`
- `DINING`
- `DECK`
- `BATHROOM`
- `CLOSET`
- `KITCHEN`
- `FP`
- `DW`
- `FLOOR 1`
- `GROSS INTERNAL AREA`
- `TOTAL`
- `LOGO HERE`
- disclaimer text

분류:

- room label: `LIVING ROOM`, `OFFICE`, `ENTRY`, `BEDROOM`, `DINING`, `BATHROOM`, `KITCHEN`
- storage label: `PANTRY`, `CLOSET`
- outdoor label: `DECK`, `VERANDA`
- fixture label: `FP`, `DW`
- floor label: `FLOOR 1`
- annotation: area note, logo, disclaimer

## 벡터 노드 추출

### Polygon

큰 면적의 채워진 polygon은 공간 표면 후보가 될 수 있다.

판단 단서:

- fill이 있음
- 면적이 큼
- 방 라벨 근처 또는 내부
- 외벽 또는 주요 경계 내부

주의:

- 하나의 큰 polygon이 여러 방의 바닥색일 수 있다.
- 공간별 polygon이 아니라 배경 영역일 수 있다.

### Rect

rect는 다양한 의미를 가질 수 있다.

가능 후보:

- 창문 segment
- 설비
- 가구 심볼
- 벽 일부
- 치수 표기 박스
- 로고 박스

분류 단서:

- 매우 얇고 벽 위에 있으면 window candidate
- 작은 반복 rect는 fixture detail
- 큰 채워진 rect는 surface candidate
- 도면 바깥쪽 rect는 annotation candidate

### Line

line은 대부분 벽, 치수선, 창문 세부선, 설비 세부선 중 하나다.

분류 단서:

- 검은 stroke, 긴 수평/수직선: wall 또는 fixture boundary
- 회색 stroke, arrow marker와 함께 있음: dimension line
- 얇은 반복 line: window detail
- fixture polygon 내부 line: fixture detail

### Path

path는 가장 해석이 어렵다.

가능 후보:

- 문 swing arc
- fixture symbol
- 로고 graphic
- 복잡한 가구 또는 설비
- 외곽선

문 후보 path 단서:

- arc 형태
- 벽 gap 근처
- 반지름이 일정
- 힌지점으로 보이는 작은 모서리와 연결
- 근처에 얇은 door leaf polygon 또는 rect가 있음

## 공간 추출

공간 entity는 라벨과 geometry를 함께 보고 만든다.

생성 조건:

- 공간 라벨이 있음
- 라벨 주변 또는 내부에 공간 표면 후보가 있음
- 공간 경계를 이루는 벽 또는 boundary가 있음

공간 추출 우선순위:

1. 라벨이 내부에 포함된 polygon
2. 라벨 중심과 가장 가까운 큰 filled polygon
3. 벽선으로 닫힌 영역
4. 색상 영역과 벽 경계의 교차로 만들어진 영역

## 벽 추출

벽은 검은색 두꺼운 선 또는 좁은 polygon으로 표현될 수 있다.

초기에는 두 종류로 나눈다.

- `wall_line_candidate`
- `wall_solid_candidate`

벽 graph 구축 단계:

1. 긴 수평/수직 line과 polygon edge 추출
2. 거의 같은 좌표의 선분 병합
3. 짧은 gap 감지
4. door/window opening 후보와 연결
5. 공간 boundary에 할당

## 문 추출

문은 다음 조합으로 판단한다.

- swing arc path
- door leaf line 또는 narrow polygon
- 벽 gap
- 두 공간 사이 위치

추출 속성:

- hinge point
- swing arc
- opening width
- connected spaces
- opens into
- swing direction
- clearance area

문 열림 방향 판단:

1. arc의 중심을 hinge point로 추정
2. arc 시작점과 끝점을 계산
3. 문짝 방향과 arc 방향을 연결
4. arc가 어느 공간 내부에 있는지 계산
5. 해당 공간을 `opensInto`로 기록

불확실하면 다음처럼 기록한다.

```json
{
  "opensInto": "unknown",
  "status": "needs_review"
}
```

## 창문 추출

창문은 보통 벽 위에 있는 얇은 선 또는 반복 사각형 패턴이다.

창문 후보 단서:

- 벽과 같은 방향으로 정렬
- 좁은 두께
- 길이가 일정 이상
- 반복된 rect 또는 line
- 외벽과 접촉
- 공간과 외부 사이에 위치

추출 속성:

- locatedOn wall
- adjacent space
- adjacent exterior
- width
- orientation
- sill side unknown
- openable unknown
- daylight source 여부
- ventilation source 여부

창문 열림 방향은 SVG 심볼만으로는 대부분 불확실하다. casement, sliding, double-hung 등의 심볼 규칙이 명확할 때만 추론한다.

## 복도와 circulation space 추론

복도는 라벨이 없을 수 있다.

복도 후보 단서:

- 길고 좁은 공간
- 여러 문에 접함
- 주요 기능 라벨이 없음
- 현관 또는 계단과 연결
- 방 사이를 연결하는 통과 공간

초기 카테고리:

- `explicit_circulation_space`: 라벨이 있는 복도, hall 등
- `inferred_circulation_space`: 형상과 연결성으로 추론
- `pass_through_space`: 거실처럼 통과 동선도 담당하는 공간

## 설비 추출

설비는 라벨과 심볼을 결합해서 추출한다.

예:

- `DW`: dishwasher appliance
- `FP`: fireplace
- bathroom fixture: 변기, 세면대, 욕조 후보
- kitchen fixture: 싱크, 카운터, 아일랜드, appliance

초기에는 모든 설비를 완벽히 분류하기보다 `fixture_candidate`로 보존하고, 라벨 또는 위치 기반으로 subtype을 부여한다.

## 주석 제거

도면 외부 주석은 공간 분석에서 제외한다.

제외 후보:

- logo 영역
- gross internal area note
- total area note
- disclaimer
- Matterport logo path
- 치수 화살표와 치수선

단, 문서 메타데이터나 면적 정보로 쓸 수 있으므로 완전히 삭제하지 않고 `Annotation`으로 분리한다.

