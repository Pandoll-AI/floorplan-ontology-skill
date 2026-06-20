# 검증과 로드맵

## 검증 원칙

자동 추출 결과는 반드시 시각적으로 검증 가능해야 한다. 이 프로젝트의 위험은 잘못된 추론이 조용히 구조화 데이터로 굳어지는 것이다.

따라서 모든 단계는 다음을 남긴다.

- 원본 SVG 원소 id
- 추론 근거
- confidence
- 검증 상태
- overlay 시각화

## 검증 산출물

### 1. Overlay SVG

원본 도면 위에 추출 결과를 덧그린다.

표시 대상:

- 공간 entity outline
- 라벨 anchor
- 라벨과 매칭된 공간 연결선
- 문 후보
- 창문 후보
- 벽 후보
- 설비 후보
- 불확실 후보

색상 예:

- 공간: 반투명 파랑
- 문: 주황
- 창문: 하늘색
- 벽: 검정
- 설비: 보라
- 주석: 회색
- 검증 필요: 빨강

### 2. Debug Report

Markdown 또는 HTML로 생성한다.

포함 내용:

- 전체 요소 수
- 태그별 요소 수
- 라벨 목록
- 공간 후보 목록
- 매칭 실패 라벨
- 라벨 없는 공간 후보
- 불확실한 문 후보
- 불확실한 창문 후보
- 분석 모듈별 제한 사항

### 3. QA JSON

기계적으로 확인할 수 있는 검증 항목이다.

```json
{
  "checks": [
    {
      "name": "all_labels_have_category",
      "status": "passed"
    },
    {
      "name": "room_labels_linked_to_space",
      "status": "warning",
      "details": ["label_veranda has no closed polygon match"]
    }
  ]
}
```

## 품질 지표

### 라벨 추출 지표

- 전체 텍스트 수
- 라벨 분류 성공률
- 방 이름과 치수 분리 성공률
- annotation 제외 성공률

### 공간 추출 지표

- room label 대비 space entity 생성률
- label-space 매칭 성공률
- 라벨 없는 공간 후보 수
- 중복 공간 후보 수

### 문/창문 추출 지표

- door candidate 수
- door entity 승격 수
- hinge 추정 성공률
- opensInto 추정 성공률
- window candidate 수
- exterior window 판정 성공률

### 관계 그래프 지표

- connected space 수
- isolated space 수
- door가 연결한 space pair 수
- exterior와 연결된 window 수
- relation confidence 평균

## MVP 계획

### MVP 1: SVG 구조화

목표:

- SVG 파싱
- style 정규화
- transform 반영
- vector node 추출
- label entity 추출

산출물:

- `vectors.json`
- `labels.json`
- `debug_report.md`

성공 기준:

- 원본 SVG의 도형 요소가 모두 누락 없이 추출된다.
- 모든 텍스트 라벨이 병합된다.
- 방 이름과 치수가 분리된다.

### MVP 2: 공간 entity 생성

목표:

- 공간 후보 분류
- 라벨과 공간 후보 매칭
- room/storage/outdoor/annotation 분리

산출물:

- `entities.json`
- `label_entity_links.json`
- `overlay.svg`

성공 기준:

- 주요 방 라벨이 공간 entity와 연결된다.
- annotation이 공간 entity로 잘못 승격되지 않는다.

### MVP 3: 벽, 문, 창문 후보

목표:

- 벽 후보 추출
- 문 swing arc 후보 추출
- 창문 반복 패턴 후보 추출
- opening graph 초안 생성

산출물:

- `openings.json`
- `walls.json`
- `relations.json`

성공 기준:

- 문과 창문이 fixture나 annotation과 분리된다.
- 문 후보가 인접 공간과 연결된다.

### MVP 4: 동선과 개구부 분석

목표:

- circulation graph 생성
- door opensInto 추론
- 주요 공간 간 접근 경로 계산
- 문 개폐 충돌 후보 계산

산출물:

- `analysis_circulation.json`
- `analysis_door_swing.json`

성공 기준:

- 현관에서 주요 공간까지의 경로가 계산된다.
- 문 swing area가 overlay에 표시된다.

### MVP 5: 통풍과 채광 가능성

목표:

- exterior boundary 추정
- 외부 창문 판정
- 공간별 daylight potential 계산
- 공간별 ventilation potential 계산

산출물:

- `analysis_daylight.json`
- `analysis_ventilation.json`

성공 기준:

- 창문이 있는 공간과 없는 공간이 구분된다.
- 외부 개구부 기반의 가능성 점수가 생성된다.

## 장기 로드맵

### 1. 온톨로지 export

JSON IR을 JSON-LD 또는 RDF로 변환한다.

예:

- `FloorPlan`
- `Space`
- `Opening`
- `Boundary`
- `Fixture`
- `SpatialRelation`
- `FunctionalRelation`

### 2. Graph DB 연동

Neo4j, RDF store, DuckDB spatial extension 등으로 확장할 수 있다.

질의 예:

```cypher
MATCH (a:Space)-[:CONNECTED_TO]->(b:Space)
WHERE a.name = "ENTRY"
RETURN b
```

### 3. LLM 기반 해석 보조

LLM은 원천 추출기가 아니라 해석 보조로 사용한다.

적합한 역할:

- 라벨 normalization
- 공간 기능 분류
- 불확실 후보 설명
- 분석 결과 요약
- 사용자 질의 응답

부적합한 역할:

- 원본 좌표 계산
- 문 swing 기하 계산
- 신뢰도 없는 임의 추측

### 4. 다중 SVG 일반화

같은 Matterport 계열 SVG 여러 개를 처리하며 규칙을 일반화한다.

필요 작업:

- class 번호에 의존하지 않기
- 색상과 geometry 패턴을 조합하기
- 파일별 scale 차이 처리
- floor 간 연결 관계 처리
- full building graph 생성

### 5. 외부 메타데이터 결합

정밀 분석을 위해 추가 데이터가 필요하다.

- 북향
- 위치와 위도
- 층고
- 창 높이
- 창 개폐 방식
- 주변 건물
- 실측 scale
- 재료 정보

## 리스크

### SVG 표현의 불안정성

같은 의미가 파일마다 다른 도형 조합으로 표현될 수 있다.

대응:

- class 번호가 아니라 geometry, style, relation 기반으로 추론
- 불확실 후보를 보존
- overlay 검증 필수화

### 의미 과잉 추론

SVG만으로 알 수 없는 정보를 확정하면 안 된다.

대응:

- `unknown`과 `requires_external_metadata` 사용
- confidence와 evidence 기록

### 닫힌 공간 추출의 어려움

방 polygon이 명시적으로 분리되어 있지 않을 수 있다.

대응:

- label 기반 space seed
- wall graph 기반 region reconstruction
- surface polygon과 boundary line 결합

### 문/창문 심볼의 다양성

문과 창문 표현이 벤더 또는 스타일에 따라 달라질 수 있다.

대응:

- 후보 기반 추출
- 여러 evidence 조합
- 확정 entity와 후보 entity 분리

## 다음 실행 권장 순서

1. `VectorNode`와 `LabelEntity` extractor 구현
2. 첫 SVG에 대해 `vectors.json`, `labels.json` 생성
3. 라벨 normalization 규칙 검증
4. 공간 후보와 라벨 매칭 구현
5. overlay SVG 생성
6. 문과 창문 후보 탐지 구현
7. relation graph 생성
8. circulation 분석부터 시작
9. ventilation과 daylight는 외부 창문 판정 이후 진행

