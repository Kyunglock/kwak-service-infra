# CI/CD 상세

## 검사 내용

### kwak-service-fe (`ci-frontend.yml`)

| 단계 | 명령 | 비고 |
|---|---|---|
| ESLint | `npm run lint` | eslint 9 flat config |
| 타입체크 | `npm run typecheck` | `tsc --noEmit`. vite 빌드는 타입을 안 본다 |
| 빌드 | `npm run build` | 배포가 Dockerfile 안에서 도는 그 빌드 |

`react-refresh/only-export-components`와 `react-hooks/exhaustive-deps`는 경고로
두었습니다(현재 21건). 에러는 0건이어야 통과합니다.

### kwak-service-be (`ci-backend.yml`)

| 단계 | 명령 | 비고 |
|---|---|---|
| 마이그레이션 규칙 | `check-migrations.py` | V번호 중복·명명 규칙 |
| 빌드+테스트 | `./gradlew build` | 테스트 31파일 / 170개 |

**Flyway는 쓰지 않습니다.** 어느 `build.gradle`에도 의존성이 없고, 마이그레이션은
`ARCHITECTURE.md` 기준 수동 실행입니다. 도구가 순서를 강제해 주지 않으므로
파일명과 버전 번호만이라도 CI에서 지킵니다. (`CLAUDE.md`의 Flyway 언급은 낡았습니다.)

테스트 중 `@SpringBootTest`는 `PortalApplicationTests` 하나뿐이고 나머지는 전부
Mockito 단위 테스트입니다. 그 하나가 전체 컨텍스트를 띄우고 HikariCP가 기동 시
커넥션을 만들기 때문에 MySQL·Redis 서비스 컨테이너를 붙였습니다.
`application.yml` / `application-local.yml`의 placeholder는 기본값이 없어서
하나라도 비면 컨텍스트가 뜨지 않으므로 전부 더미 값으로 채웁니다.

### collector (`ci-collector.yml`)

| 단계 | 명령 | 비고 |
|---|---|---|
| Ruff | `ruff check .` | E/W/F/I/B/UP |
| 테스트 | `pytest -q` | 17개 |

`test_pipeline.py`와 `test_stock_scheduler.py`는 테스트가 아니라 **진단 스크립트**입니다.
모듈 최상위에서 바로 실행되도록 작성돼 있어 import만으로 실제 DB·LLM·외부 네트워크를
때립니다. `pyproject.toml`에서 pytest 수집 대상에서 제외했습니다.

## 알려진 문제 (미해결)

### kwak-service-be 배포 파일이 레포에 없음

`deploy-compose.yml`은 `docker-compose.yml`을 요구하는데, **kwak-service-be에는
`docker-compose.yml`도 각 서비스 `Dockerfile`도 git에 없습니다.** gitignore에 있는
것도 아니고 그냥 존재하지 않습니다.

지금 배포가 도는 이유는 self-hosted 러너 작업공간에 예전에 수동으로 만든 untracked
파일이 남아 있고, `actions/checkout`이 untracked 파일을 지우지 않기 때문입니다.
러너를 새로 깔거나 작업공간을 청소하면 배포가 깨집니다.

`deploy-compose.yml`에 파일 존재 확인 단계를 넣어, 이 경우 애매한 docker 에러 대신
명확한 메시지로 실패하게 해두었습니다. **러너에 있는 실제 파일을 레포에 커밋하는 것이
근본 해결입니다.**

collector도 compose가 `env_file: .env`를 요구하는데 `.env`는 당연히 gitignore이므로
러너에 존재해야 합니다(`requires-env-file: true`로 확인).

### 검토하지 않은 것

- `ci-backend.yml`은 이 환경에서 Gradle 배포판 다운로드가 막혀 **로컬 검증을 못 했습니다.**
  fe/collector 검사는 전부 실제로 돌려서 통과를 확인했지만 be는 첫 실행에서
  조정이 필요할 수 있습니다.
- collector 배포는 **이번에 새로 생긴 동작**입니다. 기존에는 워크플로가 없었습니다.
  main에 머지되는 순간부터 push마다 배포가 돕니다. 러너와 `.env`를 먼저 확인하세요.

## 제안했지만 넣지 않은 검사

| 검사 | 왜 유용한가 |
|---|---|
| gitleaks | 시크릿 커밋 사고 방지. fe/be/infra가 public이라 특히 |
| actionlint | 워크플로 문법. 이번 파일들은 수동으로 돌려 통과 확인함 |
| hadolint | Dockerfile 린트 |
| Trivy | 이미지/의존성 CVE |

## 버전 고정

서비스 레포가 `@main`으로 호출하므로 infra 변경이 즉시 반영됩니다. 안정성이 필요해지면
태그를 끊어 `@v1` 형태로 고정하세요.
