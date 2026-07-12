# PVP.gg 전환 프로젝트

Google Apps Script와 Google Sheet로 운영하던 임시 전적 조회 사이트를 Docker 기반 웹사이트로 전환하는 프로젝트입니다.

현재 1차 목표는 기존 데이터를 안전하게 이관할 수 있는 기반을 만들고, 공개 조회 화면과 관리자 경기 입력/취소/복구 흐름을 FastAPI + PostgreSQL 위에 올리는 것입니다. 초기 개발 중에는 `AUTH_MODE=dev`로 모든 관리 기능을 검증하고, Google OAuth는 로컬에서 먼저 검증한 뒤 도메인/HTTPS 준비 시 운영에 활성화합니다.

## 기술 스택

- Backend: FastAPI, SQLAlchemy 2, Alembic
- Database: PostgreSQL
- Frontend: 정적 HTML/CSS/JS, API 연동
- Deploy: Docker Compose, OCI Free Tier 대상

## 빠른 시작

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH="backend"
pytest
uvicorn app.main:app --reload --app-dir backend
```

브라우저에서 `http://127.0.0.1:8000`을 열면 개발용 화면을 볼 수 있습니다.

Docker로는 다음처럼 시작합니다.

```powershell
docker compose up --build
```

## 참조 Excel 검사

```powershell
$env:PYTHONPATH="backend"
python -m app.scripts.inspect_legacy_workbook ".\참조정보\PVP.gg.xlsx"
```

이 명령은 원본 Workbook의 시트명, 행/열 수, 상단 헤더 후보를 JSON으로 출력합니다. 다음 단계에서 이 결과를 기반으로 실제 마이그레이션 매핑을 채웁니다.

## 참조 Excel 이관

로컬 DB에 초기 스키마를 적용한 뒤 원본 Workbook을 이관합니다.

```powershell
$env:PYTHONPATH="backend"
python -m alembic upgrade head
python -m app.scripts.import_legacy_workbook ".\참조정보\PVP.gg.xlsx"
```

현재 임포터는 시즌, 플레이어, 직업 캐릭터명, 시즌 랭킹 스냅샷, 경기 이력을 이관합니다. 종료 시즌의 점수 이벤트는 스냅샷 기준으로 보존하고, 신규 열린 시즌부터 재계산 가능한 점수 이벤트를 생성합니다.

## 현재 결정사항

- 기존 Google Sheet는 개발 중 더 이상 신규 기록이 추가되지 않습니다.
- 기존 시즌은 종료된 상태로 이관하며, 종료 시즌의 취소/복구는 허용하지 않습니다.
- 신규 시즌부터 설정된 MMR 규칙 버전을 적용합니다.
- 시즌 중 MMR 규칙 변경은 허용하지 않습니다.
- 경기 취소/복구는 열린 시즌에서만 허용하며, 삭제가 아니라 상태 변경과 감사 로그로 남깁니다.
- Google OAuth 코드는 구현해 두고 로컬 HTTP에서 검증한 뒤, 운영 도메인과 HTTPS 준비 후 활성화합니다.
- 개발/내부 검증 중에는 `AUTH_MODE=dev`로 관리자 권한을 가정합니다.

## Google OAuth 로컬 검증

Google Cloud Console의 OAuth 웹 클라이언트에 다음 리디렉션 URI를 등록합니다.

```text
http://localhost:8000/api/auth/callback/google
```

`.env`에는 다음 값을 설정합니다. 접속 주소와 콜백 주소의 호스트를 모두 `localhost`로 통일해야 세션 상태가 유지됩니다.

```text
AUTH_MODE=google
SESSION_SECRET=충분히-긴-임의의-문자열
SESSION_HTTPS_ONLY=false
GOOGLE_CLIENT_ID=발급받은-client-id
GOOGLE_CLIENT_SECRET=발급받은-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback/google
GOOGLE_SUPER_ADMIN_EMAILS=최초-super-관리자@gmail.com
```

운영 전환 시에는 HTTPS 주소로 `GOOGLE_REDIRECT_URI`를 바꾸고 `SESSION_HTTPS_ONLY=true`로 설정합니다.
