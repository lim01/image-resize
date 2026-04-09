# CentOS / Rocky Linux 실행 가이드

CentOS와 Rocky는 모두 RHEL 계열이라 명령이 거의 동일합니다.

## 1. 사전 준비 — 시스템 패키지

CentOS/Rocky 계열은 `dnf`(또는 구버전 `yum`)을 사용합니다. Pillow를 wheel(바이너리)로 설치하면 시스템 라이브러리가 필요 없지만, **소스 빌드 fallback**이나 EPEL이 막혀있는 환경을 대비해 이미지 코덱 라이브러리를 함께 깔아두는 게 안전합니다.

```bash
# Rocky 9 / Rocky 8 / CentOS Stream 공통
sudo dnf install -y git python3 python3-pip

# (선택) Pillow가 소스 빌드로 떨어질 때 필요한 dev 패키지
sudo dnf install -y gcc python3-devel \
    libjpeg-turbo-devel zlib-devel libwebp-devel libtiff-devel
```

### Python 버전 확인

```bash
python3 --version
```

| OS | 기본 Python |
|---|---|
| CentOS 7 | 3.6 ❌ (이 프로젝트 미지원, 별도 설치 필요) |
| CentOS Stream 8 / Rocky 8 | 3.6 (기본) → `dnf install python3.11` 권장 |
| CentOS Stream 9 / Rocky 9 | 3.9 ✅ |

**CentOS 7**이면 SCL(Software Collections) 또는 pyenv로 Python 3.9+를 별도 설치해야 합니다. Rocky 8에서 3.11을 설치하는 예:

```bash
sudo dnf install -y python3.11 python3.11-devel
```

## 2. 프로젝트 가져오기

```bash
git clone <리포지토리 URL> image-resize
cd image-resize
```

또는 Windows에서 작업 중이면 zip/tar로 옮긴 뒤 해제.

## 3. 의존성 설치 — 두 가지 방법

### 방법 A: uv 사용 (권장, 프로젝트 표준)

이 프로젝트는 uv로 의존성을 관리합니다.

```bash
# uv 설치 (root 권한 불필요, ~/.local/bin에 설치됨)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # 또는 새 셸 열기

# 의존성 설치 + 가상환경 자동 생성 (.venv)
uv sync
```

### 방법 B: 표준 venv + pip (uv 없이)

회사망 등에서 외부 스크립트 실행이 막혀있으면:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "Pillow>=10.0.0" "pytest>=7.0.0"
```

## 4. 동작 확인

### 테스트 실행

```bash
# uv 방식
uv run pytest

# venv 방식
source .venv/bin/activate
pytest
```

29 passed, 1 skipped가 나오면 정상입니다.

### CLI 실행

```bash
# uv
uv run python compress_images.py ./photos -q 80

# venv
python compress_images.py ./photos -q 80
```

## 5. Linux 특유 주의점

### 와일드카드 동작

**bash/zsh는 와일드카드를 셸에서 자동 확장합니다** (Windows cmd와 다름). 그래서:

```bash
# 셸이 *.jpg를 먼저 확장 → Python은 [a.jpg, b.jpg, ...] 인자를 받음
python compress_images.py *.jpg

# 셸 확장을 막고 Python 내부 glob을 쓰려면 따옴표
python compress_images.py "*.jpg"
python compress_images.py "photos/**/*.jpg"  # 재귀 glob은 따옴표 필수
```

코드는 둘 다 동작하도록 짜여 있으니(`glob.has_magic` 체크), 사용자 취향대로 쓰면 됩니다. 단 `**`를 셸이 확장하길 원하면 bash에서 `shopt -s globstar`이 필요합니다.

### 파일 권한

```bash
# 실행 파일로 만들고 싶으면 (선택)
chmod +x compress_images.py
```

쉬뱅(`#!/usr/bin/env python3`)이 없으니 직접 실행하려면 첫 줄을 추가하거나 `python compress_images.py` 형태로 호출하세요.

### 경로 구분자 / 한글 파일명

- 경로: 코드는 `pathlib.Path`만 쓰므로 자동 처리됨
- 한글: 로케일이 UTF-8이어야 안전. 확인:

  ```bash
  locale
  # LANG=ko_KR.UTF-8 또는 en_US.UTF-8 권장
  ```

  깨지면 `sudo dnf install -y glibc-langpack-ko` 후 `export LANG=ko_KR.UTF-8`.

### SELinux

기본 enforcing이어도 홈 디렉터리 안에서만 작업한다면 영향 없음. `/var` 등 시스템 경로의 이미지를 처리하면 read/write denial이 날 수 있으니 가능하면 사용자 디렉터리에서 실행.

## 6. 한 번에 정리한 셋업 스크립트 (Rocky 9 기준)

```bash
#!/usr/bin/env bash
set -euo pipefail

sudo dnf install -y git python3 python3-pip \
    gcc python3-devel libjpeg-turbo-devel zlib-devel libwebp-devel

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

git clone <repo-url> image-resize
cd image-resize
uv sync
uv run pytest
echo "Setup complete. Try: uv run python compress_images.py ./photos -q 80"
```

## 7. 트러블슈팅

| 증상 | 원인/해결 |
|---|---|
| `ModuleNotFoundError: PIL` | venv 활성화 안 됐거나 `uv sync`/`pip install` 미실행 |
| `Pillow` 빌드 실패 (`libjpeg.h: No such file`) | 1번 단계의 dev 패키지 누락 → `dnf install libjpeg-turbo-devel zlib-devel libwebp-devel` |
| `python3: command not found` | `dnf install python3` 또는 Rocky 8에서 `dnf install python3.11` 후 `python3.11`로 호출 |
| `uv: command not found` (설치 후) | `source ~/.bashrc` 또는 `export PATH="$HOME/.local/bin:$PATH"` |
| 와일드카드가 의도와 다르게 동작 | 셸 확장 vs 프로그램 내부 glob 차이 — 따옴표로 감싸 Python에게 위임 |
| 한글 파일명 깨짐 | 로케일을 UTF-8로 설정 |
| `permission denied` 출력 폴더 | 사용자 홈 안에서 작업하거나 출력 폴더를 `chmod`/`chown` |

CentOS와 Rocky는 같은 RHEL 계열이라 위 가이드가 양쪽 모두 동작합니다. 차이가 생길 수 있는 유일한 부분은 **CentOS 7**(EOL, Python 3.6 기본)인데, 이 경우 Python 3.9+를 SCL이나 pyenv로 별도 설치해야 합니다. CentOS Stream 9 / Rocky 9는 별도 설정 없이 그대로 동작합니다.
