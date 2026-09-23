# 가이드

| 페이지 | 용도 |
|---|---|
| `index.html` | 우주(궤도) 보기 |
| `list.html` | 회차별 발표 목록. `list.html#14` 처럼 회차 번호를 해시로 붙이면 그 회차가 바로 열린다 |

두 페이지 모두 `data.json` 하나를 읽는다. 재생 기록(수신 완료)도 공유한다.

## 회차 추가

### 자동: 채널에서 가져오기

```bash
python3 tools/sync_youtube.py            # 미리보기
python3 tools/sync_youtube.py --write    # data.json에 반영
```

| 옵션 | 뜻 |
|---|---|
| `--write` | 없으면 미리보기만 하고 파일을 건드리지 않는다 |
| `--presenter 이름` | 새 영상에 넣을 발표자 |
| `--keep-titles` | 직접 다듬어둔 제목을 유튜브 제목으로 덮어쓰지 않는다 |
| `--channel UC...` | 다른 채널에서 가져온다 |

RSS 피드는 최신 15개까지만 준다. 영상이 그보다 많으면 `pip install yt-dlp` 후 다시 실행하면 전체를 가져온다. 스크립트가 `yt-dlp`가 있는지 먼저 확인한다.

### 직접 넣기

`data.json`의 `sessions` 배열에 한 줄 추가한다.

```json
{ "no": 15, "date": "2026-09-17", "title": "제목", "presenter": "수양",
  "youtube": "dQw4w9WgXcQ" }
```

- `youtube` — 영상 URL의 `v=` 뒤 11글자. `https://youtu.be/dQw4w9WgXcQ` → `"dQw4w9WgXcQ"`
- 아직 녹화가 없으면 `"youtube": null`. 날짜가 미래면 "예정", 과거면 "신호 없음"으로 표시된다.

## 스터디원 추가

`data.json`의 `crew`에 한 줄 추가한다. 이름은 `sessions`의 `presenter`와 정확히 같아야 한다.
등록되지 않은 이름은 "미지의 천체"로 나오고 회색 구체가 된다.

```json
"이름": { "kind": "saturn", "texture": "textures/saturn.jpg", "glow": "#D9C08A" }
```

`kind`가 크기와 부속물을, `texture`가 표면을, `glow`가 주변에 번지는 빛 색을 결정한다.
`textures/` 안에 열 종류가 미리 들어 있어서 사람이 늘면 쓰지 않던 천체를 골라 쓰면 된다.

| kind | 천체 | 크기 | 특징 |
|---|---|---|---|
| `moon` | 달 | 0.70 | 분화구 |
| `mercury` | 수성 | 0.66 | 분화구, 가장 작음 |
| `venus` | 금성 | 0.88 | 황산 구름, 대기광 |
| `earth` | 지구 | 0.94 | 대륙과 구름, 대기광 |
| `mars` | 화성 | 0.80 | 극관, 협곡 |
| `jupiter` | 목성 | 1.36 | 가로 띠, 대적점, 가장 큼 |
| `saturn` | 토성 | 1.18 | 기울어진 고리 |
| `uranus` | 천왕성 | 1.00 | 누운 자전축, 대기광 |
| `neptune` | 해왕성 | 0.98 | 대흑점, 대기광 |
| `comet` | 혜성 | 0.56 | 태양 반대쪽으로 뻗는 꼬리 |

### 세부 조정

```json
"이름": { "kind": "earth", "texture": "textures/earth.jpg", "glow": "#5FA8D8",
          "size": 1.1, "tilt": 0.4, "atmo": 0.35 }
```

| 값 | 뜻 |
|---|---|
| `size` | 크기 배율 |
| `tilt` | 자전축 기울기 (라디안) |
| `ring` | `"tilt"` 기울어진 고리 / `"upright"` 수직 고리 / `false` 없음 (기본은 토성만 있음) |
| `tail` | `true`면 태양 반대쪽으로 꼬리 |
| `atmo` | 대기광 세기. `0`이면 없음 |

## 밝기 조절

`data.json`의 `look`.

| 값 | 역할 |
|---|---|
| `sun` | 태양광 세기. 올리면 태양을 향한 면만 밝아지고 명암 대비가 커진다 |
| `ambient` | 환경광. 모든 면을 고르게 밝히지만 올릴수록 구체가 납작해 보인다 |
| `unseen` | 아직 안 본 회차에 곱하는 색. `#FFFFFF`로 두면 시청 여부 구분이 사라진다 |

## 텍스처 교체

`textures/` 안의 파일을 같은 이름으로 덮어쓰면 된다.
**등장방형(equirectangular, 가로:세로 = 2:1)** 이미지여야 구체에 제대로 감긴다.
실제 행성 사진 맵은 NASA의 3D 리소스나 Solar System Scope에서 구할 수 있다(라이선스 확인 필요).

포함된 열 장은 `tools/generate_textures.py`로 생성한 것이다. 색, 띠 개수, 대륙 비율 같은 값을
바꿔 다시 뽑을 수 있다. 지구는 노이즈를 고도로 보고 해수면에서 잘라 대륙을 만들기 때문에,
`sea` 분위값을 바꾸면 육지 비율이 달라진다.

```bash
pip install numpy pillow
python3 tools/generate_textures.py textures
```

## 조작

| | 마우스 | 터치 |
|---|---|---|
| 시점 회전 | 드래그 | 한 손가락 드래그 |
| 확대 축소 | 스크롤 | 두 손가락 오므리기 |
| 회차 열기 | 행성 클릭 | 행성 탭 |

