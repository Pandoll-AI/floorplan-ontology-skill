# 개념 모델과 온톨로지 계층

## 기본 관점

SVG는 도형의 집합이고, 평면도는 공간 의미의 집합이다. 둘 사이에는 직접적인 1:1 대응이 없다.

예를 들어 하나의 방은 하나의 `polygon`일 수도 있고, 여러 벽선과 바닥색, 텍스트 라벨이 결합된 결과일 수도 있다. 반대로 하나의 `path`는 문 호일 수도 있고, 로고 일부일 수도 있고, 가구 심볼일 수도 있다.

따라서 데이터 모델은 다음 네 계층을 분리한다.

```text
Raw SVG Layer
Normalized Geometry Layer
Semantic Entity Layer
Spatial / Functional Graph Layer
```

## 계층 구조

### 1. Raw SVG Layer

원본 SVG DOM에 가까운 계층이다.

- 원본 태그명
- 원본 attribute
- class
- style
- transform
- DOM 순서
- 원본 파일명

이 계층은 추적성과 디버깅을 위해 보존한다.

### 2. Normalized Geometry Layer

SVG 요소를 공통 기하 구조로 변환한 계층이다.

대표 객체는 `VectorNode`다.

- `rect`는 polygon으로 변환 가능
- `line`은 segment로 변환
- `polyline`은 line string으로 변환
- `polygon`은 polygon으로 변환
- `path`는 path command 또는 근사 geometry로 변환
- 모든 transform은 좌표에 반영
- bbox, centroid, area, length를 계산

### 3. Semantic Entity Layer

기하 요소와 라벨을 해석해서 의미 객체로 만든 계층이다.

대표 entity:

- `Space`
- `Wall`
- `Door`
- `Window`
- `Opening`
- `Fixture`
- `Annotation`
- `Dimension`

이 계층부터는 SVG 태그가 아니라 건축적 의미를 가진다.

### 4. Spatial / Functional Graph Layer

entity 사이의 관계를 표현하는 계층이다.

대표 관계:

- `contains`
- `locatedIn`
- `adjacentTo`
- `connects`
- `boundedBy`
- `opensInto`
- `locatedOn`
- `admitsLightTo`
- `enablesVentilationFor`
- `partOf`

이 계층이 생겨야 동선, 통풍, 채광, 기능성 분석이 가능해진다.

## 핵심 타입

### VectorNode

SVG 원소에서 나온 벡터 원자 단위다. 아직 의미 객체는 아니다.

예:

- polygon
- rect
- path
- line
- circle
- ellipse
- text anchor

### LabelEntity

SVG 텍스트에서 나온 라벨 객체다.

예:

- `LIVING ROOM`
- `24'4" x 18'0"`
- `FLOOR 1`
- `GROSS INTERNAL AREA`
- `DW`
- `FP`

라벨은 공간, 설비, 주석, 치수 등으로 분류된다.

### SpatialEntity

도면에서 의미를 가진 공간 및 건축 객체다.

예:

- `Room`
- `OutdoorArea`
- `Storage`
- `CirculationSpace`
- `Wall`
- `Door`
- `Window`
- `Appliance`
- `Fixture`

### Relation

entity 사이의 관계다.

예:

```json
{
  "type": "connects",
  "from": "door_001",
  "to": ["space_entry", "space_living_room"]
}
```

## 카테고리 체계

### Space

공간 사용 목적을 가진 entity다.

- `Room`
- `LivingSpace`
- `Bedroom`
- `Kitchen`
- `Bathroom`
- `Storage`
- `CirculationSpace`
- `OutdoorArea`
- `UtilitySpace`

### Structure

물리적 구조를 나타낸다.

- `Wall`
- `Boundary`
- `Column`
- `Stair`
- `Railing`

### Opening

공간 사이 또는 내부와 외부 사이를 연결하는 요소다.

- `Door`
- `Window`
- `Opening`
- `SlidingOpening`
- `ExteriorOpening`

### Fixture

공간의 기능을 설명하는 설비나 고정 요소다.

- `KitchenFixture`
- `BathroomFixture`
- `Appliance`
- `Fireplace`
- `ClosetSystem`
- `FurnitureSymbol`

### Annotation

도면 해석에는 도움이 되지만 공간 객체가 아닌 정보다.

- `RoomLabel`
- `DimensionLabel`
- `AreaNote`
- `FloorLabel`
- `Disclaimer`
- `Logo`

## 확실성 모델

도면 해석은 추론을 포함하므로 모든 entity와 relation은 확실성 정보를 가져야 한다.

```json
{
  "confidence": 0.86,
  "evidence": ["label_inside_polygon", "style_fill_match", "geometry_contains_text"],
  "status": "inferred"
}
```

권장 상태값:

- `observed`: 원본 SVG에서 직접 관찰됨
- `inferred`: 규칙이나 모델로 추론됨
- `ambiguous`: 후보가 여러 개임
- `needs_review`: 사람 검증 필요
- `unknown`: 현재 정보로 판단 불가

## 장기 온톨로지 방향

초기에는 JSON 기반 중간 표현을 사용하고, 안정화 후 JSON-LD 또는 RDF로 확장한다.

장기적으로는 다음 구조로 확장할 수 있다.

```text
FloorPlan
  hasFloor
  hasSpace
  hasBoundary
  hasOpening
  hasFixture
  hasAnnotation

Space
  hasLabel
  hasGeometry
  adjacentTo
  connectedTo
  contains
  boundedBy

Opening
  connects
  locatedOn
  opensInto
  enablesPassage
  enablesVentilation
  admitsLight
```

