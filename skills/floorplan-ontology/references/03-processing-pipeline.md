# 작업 파이프라인

## 전체 흐름

```text
Input SVG
 -> Parse
 -> Normalize
 -> Extract Vector Nodes
 -> Extract Labels
 -> Classify Candidates
 -> Match Labels to Geometry
 -> Build Entities
 -> Build Relations
 -> Run Analysis
 -> Export IR / Ontology / Overlay
```

## 0. 입력 관리

입력 SVG마다 `Document` 메타데이터를 만든다.

- 파일명
- viewBox
- width, height
- 좌표계
- 생성 도구 추정
- 파싱 시각
- 처리 버전

초기 대상:

```text
Matterport Sample_FCL Floor1.svg
```

## 1. SVG 파싱

목표는 원본 DOM을 잃지 않고 구조적으로 읽는 것이다.

수집 대상:

- `svg`
- `g`
- `defs`
- `style`
- `text`
- `tspan`
- `rect`
- `polygon`
- `polyline`
- `line`
- `path`
- `circle`
- `ellipse`

산출물:

- raw element list
- DOM order
- parent group
- raw attributes
- source element id

## 2. 스타일 정규화

SVG의 class 기반 스타일을 각 요소에 적용 가능한 형태로 펼친다.

처리 항목:

- class selector 파싱
- fill
- stroke
- stroke-width
- font-family
- font-size
- fill-rule
- stroke-miterlimit
- opacity

산출물:

```json
{
  "sourceElementId": "svg_el_0123",
  "computedStyle": {
    "fill": "#d9cabf",
    "stroke": "#000",
    "strokeWidth": 0.72
  }
}
```

## 3. Transform 정규화

모든 좌표는 절대 좌표계로 변환한다.

처리 대상:

- `translate`
- `rotate`
- `scale`
- `matrix`

원칙:

- 원본 transform은 보존한다.
- 계산용 geometry는 transform이 반영된 좌표를 사용한다.
- text anchor도 transform 반영 좌표를 가진다.

## 4. Vector Node 추출

SVG 도형을 공통 구조의 `VectorNode`로 변환한다.

기본 속성:

- id
- source element id
- geometry type
- points or path commands
- bbox
- centroid
- area
- length
- style
- transform
- layer
- z-order

초기 분류 후보:

- `space_surface_candidate`
- `wall_candidate`
- `door_candidate`
- `window_candidate`
- `fixture_candidate`
- `dimension_marker_candidate`
- `annotation_graphic_candidate`

## 5. Label Entity 추출

`text`와 `tspan`을 병합해 라벨을 만든다.

처리 항목:

- tspan 순서 보존
- text content 병합
- 줄바꿈 또는 tspan offset 해석
- label anchor 계산
- font size와 orientation 계산
- room name과 dimension 분리

예:

```text
LIVING ROOM24'4" x 18'0"
```

정규화 결과:

```json
{
  "name": "LIVING ROOM",
  "dimensionText": "24'4\" x 18'0\""
}
```

## 6. 후보 분류

각 vector node와 label을 규칙 기반으로 1차 분류한다.

분류 단서:

- fill color
- stroke color
- stroke width
- 면적
- 길이
- aspect ratio
- path command 형태
- 반복 패턴
- 라벨 근접성
- 공간 내부 포함 여부
- 외벽과 접촉 여부

## 7. 라벨과 geometry 매칭

라벨은 가장 가까운 공간 후보 또는 라벨을 포함하는 공간 후보와 연결한다.

우선순위:

1. 라벨 anchor가 polygon 내부에 있음
2. 라벨 bbox 중심이 polygon 내부에 있음
3. 라벨과 polygon centroid가 가까움
4. 라벨 orientation과 공간 후보 orientation이 일치
5. 치수 텍스트가 공간 크기와 대략 일치

산출물:

```json
{
  "labelId": "label_living_room",
  "entityId": "space_living_room",
  "confidence": 0.91,
  "evidence": ["label_inside_polygon", "room_name_pattern"]
}
```

## 8. Entity 생성

후보를 의미 객체로 승격한다.

생성 대상:

- space
- wall
- door
- window
- opening
- fixture
- annotation

승격 조건은 카테고리마다 다르다.

예:

- 공간은 면적이 있고 라벨 또는 경계가 있어야 한다.
- 문은 벽 위 또는 경계 근처에 있으며 swing arc 또는 opening gap을 가져야 한다.
- 창문은 벽 위에 있고 얇은 반복 선 또는 사각형 패턴을 가진다.

## 9. Relation 생성

entity 사이 관계를 계산한다.

관계 예:

- room `boundedBy` wall
- wall `hasOpening` door
- door `connects` room A and room B
- window `locatedOn` wall
- window `admitsLightTo` room
- fixture `locatedIn` room
- room `adjacentTo` room

## 10. 분석 실행

관계 그래프를 기반으로 분석한다.

초기 분석:

- circulation graph
- door swing analysis
- window placement analysis
- ventilation potential
- daylight potential
- access convenience
- privacy gradient

## 11. 검증 산출물 생성

자동 추출은 반드시 시각 검증이 가능해야 한다.

권장 산출물:

- `vectors.json`
- `labels.json`
- `entities.json`
- `relations.json`
- `analysis.json`
- `overlay.svg`
- `debug_report.md`

overlay는 다음을 색상으로 표시한다.

- 공간 entity
- 라벨 연결선
- 문 후보
- 창문 후보
- 불확실 후보
- 검증 필요 객체

