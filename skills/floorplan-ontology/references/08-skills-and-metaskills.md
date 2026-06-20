# 스킬과 메타스킬 운영 구조

이 프로젝트는 단순 SVG 파서가 아니라 추출, 해석, 제안, 검증을 반복하는 시스템이다. 따라서 작업을 다음 스킬 세트로 나눈다.

## 실제 사용 스킬

| 구분 | 파일 | 역할 |
| --- | --- | --- |
| 메타스킬 | `skills/floorplan-ontology/evidence-governance/SKILL.md` | evidence, confidence, uncertainty, vocabulary 통제 |
| 도면 진단 | `skills/floorplan-ontology/svg-forensics/SKILL.md` | SVG tag/style/transform/repeated geometry 조사 |
| 온톨로지 추출 | `skills/floorplan-ontology/ontology-extraction/SKILL.md` | label, vector node, entity, relation 생성 |
| 공간 성능 분석 | `skills/floorplan-ontology/spatial-analysis/SKILL.md` | 동선 graph, 통풍 proxy, 채광 proxy, 프라이버시 계산 |
| 리노베이션 제안 | `skills/floorplan-ontology/renovation-proposal/SKILL.md` | 변경 지시를 operation graph로 변환 |
| 시각 검증 | `skills/floorplan-ontology/visual-qa/SKILL.md` | overlay SVG, report HTML, preview 기반 QA |

## 기본 조합

새 SVG를 처음 처리할 때:

```text
evidence-governance
 + svg-forensics
 + ontology-extraction
 + visual-qa
```

추출 결과가 틀렸을 때:

```text
evidence-governance
 + svg-forensics
 + ontology-extraction
 + visual-qa
```

동선, 통풍, 채광, 프라이버시를 분석할 때:

```text
evidence-governance
 + spatial-analysis
 + visual-qa
```

이 조합에서는 숫자 산출만 허용하지 않는다. `analysis_spatial_performance.json`과 함께 `analysis_spatial_overlay.svg`, `analysis_spatial_report.html`을 만들어야 한다.

구조 변경안을 만들 때:

```text
evidence-governance
 + renovation-proposal
 + spatial-analysis
 + visual-qa
```

## 이론 사용 기준

### 사람 동선

그래프 네트워크 모델을 사용한다.

- 공간, 문, 계단, 엔트리를 node로 둔다.
- 연결 가능성을 edge로 둔다.
- 거리, 회전, 문 통과, 폭, 충돌, 프라이버시를 edge weight로 둔다.
- 최단경로, betweenness centrality, articulation point, bottleneck risk를 계산한다.
- overlay에서는 node, edge, 최단경로, 병목, 막힌 경로를 색과 선 굵기로 표시한다.

### 통풍

초기에는 full CFD가 아니라 airflow graph proxy를 사용한다.

- 방은 air-volume node다.
- 창문, 문, 개구부는 airflow edge다.
- 외부는 exterior node다.
- 가능하면 다음 압력차 기반 유량식을 쓴다.

```text
Q = Cd * A * sqrt(2 * abs(deltaP) / rho)
deltaP = 0.5 * rho * V^2 * (Cp_windward - Cp_leeward)
ACH = 3600 * Q / roomVolume
```

scale, opening area, wind direction, operability가 없으면 `ventilationPotential`만 계산하고 `unknowns`를 남긴다.

overlay에서는 외부 개구부, 가능한 airflow path, cross ventilation path, 불확실 개구부를 별도 레이어로 표시한다.

### 채광

초기에는 정밀 daylight simulation이 아니라 aperture-area proxy와 daylight factor 개념을 사용한다.

```text
DF = (Ein / Eout) * 100
Ein_avg ≈ Eout * Tvis * windowArea * utilizationFactor * maintenanceFactor / roomFloorArea
WWR = windowArea / exteriorWallArea
daylightDepth ≈ 1.5 to 2.5 * windowHeadHeight
```

orientation, glazing transmittance, exterior obstruction, real scale이 없으면 `daylightPotential`로만 보고한다.

overlay에서는 창문 aperture, daylight depth band, 약한 채광 영역, 입력값 부족 경고를 표시한다.

## 운영 원칙

- 물리 공식을 쓰되, 입력값이 없으면 근사 점수와 불확실성을 분리한다.
- 모든 분석 점수는 시각화 레이어와 함께 제공한다.
- 구조 변경안은 원본 SVG를 직접 변경하지 않고 proposal operation으로 기록한다.
- 모든 추론은 JSON, overlay, HTML에서 같은 ID로 따라갈 수 있어야 한다.
- 시각 QA에서 발견한 오류는 산출물 수동 편집이 아니라 코드와 테스트 수정으로 반영한다.
