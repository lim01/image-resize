# 이미지 압축 도구 설계 (Image Compression Tool)

- 작성일: 2026-04-08
- 상태: 승인 완료 (구현 대기)

## 1. 목적

지정한 폴더 내의 이미지(JPEG/PNG/WebP)를 **원본 가로·세로 해상도를 그대로 유지**한 채 재인코딩하여 파일 용량을 줄이는 Python CLI 도구를 만든다. 결과물은 입력 폴더와 별도의 출력 폴더에 동일한 파일명·동일한 하위 디렉터리 구조로 저장한다.

본 도구는 "리사이징"이 아니라 **재인코딩 기반 무손실/저손실 압축**이 핵심이다.

## 2. 범위

### 포함
- JPEG, PNG, WebP 파일의 재인코딩 압축
- 재귀적 폴더 탐색
- 별도 출력 폴더로의 미러링 저장
- CLI 인터페이스
- 처리 통계 출력

### 제외 (Out of scope)
- 이미지 해상도 변경(리사이즈)
- 포맷 변환 (JPEG → WebP 등)
- GUI
- 병렬 처리 (향후 확장 여지)
- AVIF, HEIC 등 추가 포맷

## 3. 기술 스택

- Python 3.9+
- **Pillow** (이미지 인코딩)
- 표준 라이브러리: `argparse`, `pathlib`, `logging`, `shutil`

## 4. 동작 흐름

```
input_dir/                      output_dir/ (예: input_dir_compressed/)
├── a.jpg              ──►      ├── a.jpg          (재인코딩)
├── sub/                        ├── sub/
│   ├── b.png          ──►      │   ├── b.png      (optimize)
│   └── c.webp         ──►      │   └── c.webp     (재인코딩)
```

1. 입력 폴더를 재귀적으로 탐색
2. 지원 확장자(JPEG/PNG/WebP)만 선별
3. 출력 폴더에 동일한 디렉터리 구조 생성
4. 각 파일을 포맷별 옵션으로 재인코딩하여 저장
5. 압축 결과가 원본보다 클 경우 옵션에 따라 원본을 복사
6. 처리 종료 시 통계 출력

## 5. CLI 인터페이스

```
python compress_images.py <input_dir> [options]

위치 인자:
  input_dir              압축할 이미지가 있는 입력 폴더

옵션:
  -o, --output DIR       출력 폴더 (기본값: <input_dir>_compressed)
  -q, --quality INT      JPEG/WebP 품질 (기본값: 85, 범위 1~100)
  --no-png-optimize      PNG optimize 비활성화 (기본: 활성화)
  --no-keep-larger       압축 후 더 커지면 원본을 복사하지 않고 압축본 유지
                         (기본: 원본보다 크면 원본 복사)
  --dry-run              실제 저장 없이 시뮬레이션만 수행
  -v, --verbose          상세 로그 출력
```

기본 사용 예시:
```bash
python compress_images.py ./photos
python compress_images.py ./photos -o ./photos_min -q 80
```

## 6. 모듈 구성

단일 파일 `compress_images.py`로 구성한다. (규모상 분리 불필요)

| 함수 | 책임 |
|---|---|
| `iter_images(root: Path) -> Iterator[Path]` | 재귀적으로 지원 확장자 파일 경로를 yield |
| `mirror_path(src: Path, in_root: Path, out_root: Path) -> Path` | 입력 경로를 출력 폴더 기준 경로로 변환 |
| `compress_one(src: Path, dst: Path, quality: int, png_optimize: bool) -> tuple[int, int]` | 단일 파일 압축. (원본 크기, 결과 크기) 반환 |
| `main()` | argparse 파싱, 루프 실행, 통계 출력 |

각 함수는 단일 책임을 가지며 독립적으로 테스트 가능하다.

## 7. 포맷별 인코딩 옵션

| 포맷 | 확장자 | Pillow 저장 옵션 |
|------|---|---|
| JPEG | `.jpg`, `.jpeg` | `quality=Q, optimize=True, progressive=True, exif=<원본 exif>` |
| PNG  | `.png` | `optimize=True, compress_level=9` |
| WebP | `.webp` | `quality=Q, method=6` |

- JPEG의 EXIF 메타데이터는 원본에서 추출(`img.info.get('exif')`)하여 보존한다.
- PNG는 무손실 압축이며 `quality` 인자의 영향을 받지 않는다.
- WebP의 `method=6`은 가장 느리지만 압축률이 가장 높은 옵션이다.

## 8. 에러 처리

| 상황 | 처리 |
|---|---|
| 깨진 이미지 / Pillow 디코딩 실패 | 경고 로그 출력 후 해당 파일 스킵, 다음 파일 진행 |
| 출력 폴더 생성 실패 (권한 등) | 에러 로그 출력 후 즉시 종료 (exit code 1) |
| 입력 폴더 미존재 | argparse 단계에서 검증 후 종료 |
| 지원하지 않는 확장자 | 조용히 스킵 (verbose 모드에서만 로그) |

## 9. 통계 출력

처리 종료 후 다음 정보를 출력한다.

```
Processed: 42 files
Skipped:   3 files
Original size:   12.4 MB
Compressed size:  4.8 MB
Saved:            7.6 MB (61.3%)
```

## 10. 테스트

`tests/test_compress_images.py`에 pytest 기반 테스트 작성.

테스트 케이스:
1. **기본 동작**: 샘플 폴더 압축 시 출력 폴더 구조가 입력과 동일한지
2. **파일 크기**: 결과 파일이 원본보다 작거나 같은지 (keep-larger 모드 기준)
3. **재귀 처리**: 중첩된 하위 폴더의 이미지도 처리되는지
4. **깨진 파일**: 손상된 이미지가 스킵되고 다른 파일은 정상 처리되는지
5. **dry-run**: 어떤 파일도 생성되지 않는지
6. **EXIF 보존**: JPEG 처리 후 EXIF가 유지되는지
7. **지원되지 않는 확장자**: `.txt` 등이 무시되는지

테스트용 샘플 이미지는 `tests/fixtures/`에 소량 포함하거나, conftest에서 Pillow로 동적 생성한다.

## 11. 디렉터리 구조

```
image-resize/
├── compress_images.py
├── README.md
├── requirements.txt          # Pillow, pytest
├── tests/
│   ├── conftest.py
│   ├── test_compress_images.py
│   └── fixtures/             # 또는 동적 생성
└── docs/
    └── superpowers/specs/
        └── 2026-04-08-image-compression-design.md
```

## 12. 향후 확장 (현재 범위 외)

- 멀티프로세싱을 통한 병렬 처리
- AVIF/HEIC 지원
- 진행률 표시 (tqdm)
- 설정 파일(YAML/TOML) 지원
- 포맷 변환 모드
