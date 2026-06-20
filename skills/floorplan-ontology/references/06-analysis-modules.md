# 공간 분석 모듈

## 분석의 위치

문, 창문, 복도, 동선, 통풍, 채광 분석은 SVG 파싱 직후에 바로 수행하지 않는다. 먼저 공간 그래프가 있어야 한다.

```text
Vector Nodes
 -> Entities
 -> Spatial Relations
 -> Affordance Graph
 -> Analysis Modules
```

## Affordance Graph

Affordance graph는 공간이 어떻게 사용될 수 있는지를 나타내는 그래프다.

예:

- 사람은 문을 통해 공간 A에서 공간 B로 이동할 수 있다.
- 창문은 외부 공기와 빛을 특정 공간에 제공할 수 있다.
- 문이 열리면 특정 영역을 점유한다.
- 좁은 통로는 이동 병목이 될 수 있다.

## 동선 분석

### 입력

- space entities
- door entities
- opening entities
- circulation space candidates
- blocked area candidates
- fixture locations

### 그래프 모델

공간은 node, 문과 개구부는 edge로 표현한다.

```text
ENTRY -- door_001 -- LIVING ROOM -- opening_002 -- KITCHEN
```

### 분석 항목

- 현관에서 주요 공간까지의 경로
- 침실에서 욕실까지의 경로
- 주방에서 식당까지의 경로
- 거실과 외부 공간 연결성
- 통과해야 하는 공간 수
- 병목 가능성
- dead-end 공간
- private space와 public space의 분리 정도

### 산출 예

```json
{
  "type": "circulation_path",
  "from": "space_entry",
  "to": "space_kitchen",
  "path": ["space_entry", "door_001", "space_living_room", "opening_004", "space_kitchen"],
  "doorCount": 1,
  "throughPrivateSpace": false,
  "score": 0.82
}
```

## 문 개폐 분석

### 입력

- door hinge point
- door swing arc
- door leaf direction
- connected spaces
- nearby walls
- nearby fixtures
- circulation paths

### 분석 항목

- 어느 공간으로 열리는가
- 시계 방향 또는 반시계 방향인가
- 문이 열릴 때 점유하는 영역
- 다른 문과 충돌하는가
- 벽, 가구, 설비와 충돌하는가
- 주요 동선을 가로막는가
- 유효 통과 폭이 충분한가

### 문 열림 영역

문이 열릴 때의 점유 영역을 sector polygon으로 근사한다.

```json
{
  "doorId": "door_001",
  "swingArea": {
    "type": "Sector",
    "center": [1365.72, 1628.07],
    "radius": 79.13,
    "startAngle": 180,
    "endAngle": 270
  }
}
```

## 창문 분석

### 입력

- window entities
- wall entities
- exterior boundary
- adjacent spaces
- window width
- orientation

### 분석 항목

- 어떤 공간에 창문이 있는가
- 외부와 접하는 창문인가
- 창문이 있는 벽 방향은 무엇인가
- 공간 크기 대비 창문 길이가 충분한가
- 창문이 한쪽에만 몰려 있는가
- 창문이 통풍 또는 채광 source가 될 수 있는가

### 열림 방향

창문 열림 방향은 SVG만으로 확정하기 어렵다. 다음 단계로 나눈다.

- 명확한 심볼이 있으면 추론
- sliding window처럼 방향성이 약하면 `openingDirection: "not_applicable_or_unknown"`
- 외부 데이터가 필요하면 `requires_external_metadata`

## 통풍 분석

### 기본 관점

통풍은 외부 개구부와 내부 연결성이 만드는 가능성 그래프다.

```text
Exterior
 -> Window
 -> Room
 -> Door/Open Passage
 -> Room
 -> Window
 -> Exterior
```

### 입력

- windows connected to exterior
- doors and openings
- connected space graph
- door openability
- window openability
- space size

### 분석 항목

- 외부 창문이 있는 공간
- 서로 다른 외부 개구부를 가진 공간
- cross ventilation 가능성
- 내부 깊은 공간의 환기 취약성
- 문을 열었을 때 형성되는 공기 경로
- 창문 없는 공간

### 점수 예

```json
{
  "spaceId": "space_living_room",
  "ventilationPotential": {
    "score": 0.76,
    "factors": {
      "hasExteriorWindow": true,
      "hasMultipleOpenings": true,
      "connectedToOtherWindowedSpace": true,
      "crossVentilationLikely": "unknown"
    }
  }
}
```

정밀한 통풍 분석에는 풍향, 창문 높이, 개폐 면적, 압력 차, 주변 환경 정보가 필요하다. SVG 기반 분석은 가능성 평가로 제한한다.

## 채광 분석

### 기본 관점

채광은 창문, 외벽, 공간 깊이, 방향 정보의 조합이다.

SVG만 있을 때는 절대 일조량이 아니라 `daylight potential`을 평가한다.

### 입력

- exterior windows
- window width
- window orientation
- room geometry
- distance from window to room centroid
- depth ratio
- north arrow 또는 orientation metadata

### 분석 항목

- 창문이 있는 공간
- 외부와 직접 접한 공간
- 창문 길이 대비 공간 면적
- 방 중심까지의 거리
- 깊고 좁은 공간 여부
- 창문이 한쪽 끝에 치우쳤는지 여부
- 방향 정보가 있을 경우 일조 방향 추정

### 산출 예

```json
{
  "spaceId": "space_bedroom",
  "daylightPotential": {
    "score": 0.64,
    "windowCount": 1,
    "exteriorWindowWidth": 206.5,
    "roomDepthToWindowRatio": 2.1,
    "requiresOrientationMetadata": true
  }
}
```

정밀한 채광 분석에는 북향, 위도, 날짜, 시간, 주변 건물, 창 높이, 유리 투과율이 필요하다.

## 기능적 이해

기능적 이해는 공간 이름과 설비, 연결 관계를 함께 본다.

예:

- `KITCHEN`에 `DW`가 있으면 appliance relation 생성
- `BATHROOM`에 plumbing fixture가 있으면 wet area 확정
- `ENTRY`가 여러 공간으로 연결되면 circulation hub
- `BEDROOM`과 `BATHROOM`의 접근 경로를 privacy 관점에서 평가
- `KITCHEN`과 `DINING`의 근접성을 평가

### 기능 관계 예

```json
{
  "type": "functionalAdjacency",
  "from": "space_kitchen",
  "to": "space_dining",
  "function": "food_service",
  "score": 0.88
}
```

## 구조적 이해

구조적 이해는 벽, 경계, 개구부, 외부 접점을 본다.

분석 항목:

- 외벽과 내벽 구분
- load-bearing 여부는 SVG만으로 판단하지 않음
- 큰 개구부와 작은 개구부 구분
- 공간을 나누는 주요 벽선
- 외부와 접하는 면
- 구조적으로 닫힌 공간과 열린 공간

## 분석 결과의 품질 등급

모든 분석은 품질 등급을 가져야 한다.

- `high`: geometry와 label 모두 명확함
- `medium`: geometry는 명확하지만 일부 의미가 추론됨
- `low`: 후보는 있으나 검증 필요
- `blocked`: 필요한 원천 정보가 없음

예:

```json
{
  "module": "daylight",
  "quality": "medium",
  "limitations": ["no_north_orientation", "no_window_height"]
}
```

