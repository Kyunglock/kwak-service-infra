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

### self-hosted 러너가 등록돼 있지 않다 (배포 전체가 막혀 있음)

**배포는 지금까지 한 번도 실행된 적이 없습니다.** 워크플로 실행 이력을 보면:

- `kwak-service-fe` — `Deploy Frontend` 18회 전부 `cancelled`
- `kwak-service-be` — `Deploy Backend` 29회 전부 `cancelled`

모두 `created_at` 과 `updated_at` 간격이 정확히 24시간입니다. GitHub 이 러너를
못 잡은 job 을 24시간 뒤 자동 취소한 것으로, 레포 첫 커밋(2026-06-22)부터
지금까지 `self-hosted` 라벨을 가진 러너가 job 을 가져간 적이 없습니다.
운영 컨테이너는 서버에서 수동으로 띄운 것으로 보입니다.

즉 CI 를 붙이기 전에도 배포 자동화는 동작하지 않고 있었습니다. 러너를 등록하기
전까지는 새 `deploy` job 도 똑같이 24시간 대기 후 취소됩니다.

러너 등록은 서버에서 직접 해야 합니다 (레포 Settings → Actions → Runners →
New self-hosted runner 가 주는 토큰 사용). `actions/checkout@v7` 은 러너
v2.327.1 이상을 요구하므로, 새로 받는 러너면 문제없습니다.

그래서 각 레포 `ci.yml` 의 `deploy` job 은 **수동 실행 전용**으로 두었습니다:

```yaml
if: github.ref == 'refs/heads/main' && github.event_name == 'workflow_dispatch'
```

main 에 push 해도 검사만 돌고 배포 job 은 건너뜁니다. 배포하려면 Actions 탭에서
**Run workflow** 로 `main` 을 골라 실행합니다. `main` 이 아닌 브랜치를 골라 실행하면
`github.ref` 조건에 걸려 배포는 건너뛰고 검사만 돕니다.

러너를 등록한 뒤 push 자동 배포로 되돌리려면 조건을
`github.event_name != 'pull_request'` 로 바꾸면 됩니다.

### kwak-service-be 배포 파일이 레포에 없음

`deploy-compose.yml`은 `docker-compose.yml`을 요구하는데, **kwak-service-be에는
`docker-compose.yml`도 각 서비스 `Dockerfile`도 git에 없습니다.** gitignore에 있는
것도 아니고 그냥 존재하지 않습니다.

러너 작업공간에 손으로 만들어 두는 것으로는 해결되지 않습니다 —
`actions/checkout`은 `clean` 입력이 기본 `true`라 job 시작 시 `git clean -ffdx`로
작업공간을 비웁니다. 레포에 커밋되어 있어야 합니다.

배포 job 이 실행된 적이 없어서 아직 드러나지 않았을 뿐입니다.
러너를 등록하는 순간 `docker compose` 가 파일을 못 찾고 실패합니다.

`deploy-compose.yml`에 파일 존재 확인 단계를 넣어, 이 경우 애매한 docker 에러 대신
명확한 메시지로 실패하게 해두었습니다. **러너에 있는 실제 파일을 레포에 커밋하는 것이
근본 해결입니다.**

collector도 compose가 `env_file: .env`를 요구하는데 `.env`는 당연히 gitignore이므로
러너에 존재해야 합니다(`requires-env-file: true`로 확인).

### 검토하지 않은 것

- 세 레포의 검사 워크플로는 모두 GitHub Actions 에서 실제로 돌려 통과를 확인했습니다
  (fe 38초, collector 35초, be 2분 46초). be 는 MySQL·Redis 서비스 컨테이너로
  `PortalApplicationTests` 의 컨텍스트 기동까지 확인됐습니다.
- **배포 워크플로는 아직 한 번도 실행되지 않았습니다** — 러너가 없어서입니다.
- collector 배포는 **이번에 새로 생긴 동작**입니다. 기존에는 워크플로가 없었습니다.
  main에 머지되는 순간부터 push마다 배포가 돕니다. 러너와 `.env`를 먼저 확인하세요.

## 제안했지만 넣지 않은 검사

| 검사 | 왜 유용한가 |
|---|---|
| gitleaks | 시크릿 커밋 사고 방지. fe/be/infra가 public이라 특히 |
| actionlint | 워크플로 문법. 이번 파일들은 수동으로 돌려 통과 확인함 |
| Dependabot | 액션 버전 자동 갱신. Node 20 지원 중단 같은 건을 알아서 올려줌 |
| hadolint | Dockerfile 린트 |
| Trivy | 이미지/의존성 CVE |

## 버전 고정

서비스 레포가 `@main`으로 호출하므로 infra 변경이 즉시 반영됩니다. 안정성이 필요해지면
태그를 끊어 `@v1` 형태로 고정하세요.

## 러너 보안

public 레포 + self-hosted 러너 조합의 위험과, 러너를 붙이기 전에 해야 할
레포 설정은 `RUNNER-SECURITY.md` 에 정리했습니다. 워크플로 조건만으로는
fork PR 을 막을 수 없습니다.

## 미룬 것: 날짜 의존 flaky 테스트

`FortuneServiceTest` 와 `TradeCaptureServiceTest` 는

```java
private static final LocalDate TODAY = LocalDate.now(ZoneId.of("Asia/Seoul"));
```

로 **클래스 로드 시점에** 날짜를 고정하는데, 프로덕션(`FortuneServiceImpl`,
`TradeCaptureServiceImpl`)은 호출 시점에 `LocalDate.now(KST)` 를 구합니다.
테스트 실행 중 KST 자정을 넘기면 스텁 키와 실제 인자가 어긋나 깨집니다.

2026-09-22 의 main 빌드(`d6ffe89`)가 실제로 이것으로 실패했습니다 — PR 브랜치
(`766d107`)와 트리가 완전히 동일한데 빌드 시각이 KST 23:57:58~00:00:18 로
자정을 걸쳤습니다.

고치려면 두 서비스에 `Clock` 을 주입해야 합니다. `TradeCaptureServiceTest` 는
미래 날짜 보정과 과거 날짜 보존을 실제로 단언하고 있어 `any(LocalDate.class)`
매처로 뭉개면 테스트가 무의미해집니다.

## 액션 버전

모든 액션을 Node 24 런타임을 쓰는 메이저로 올려두었습니다 (2026-09 기준 최신).

| 액션 | 버전 | 런타임 |
|---|---|---|
| actions/checkout | v7 | node24 |
| actions/setup-node | v7 | node24 |
| actions/setup-python | v7 | node24 |
| actions/setup-java | v6 | node24 |
| actions/upload-artifact | v7 | node24 |
| gradle/actions/setup-gradle | v6 | node24 |

러너는 2026-09-16 에 Node 20 을 제거했습니다. 구버전 액션을 쓰면 경고가 뜨거나
동작하지 않습니다. `actions/checkout@v7` 은 self-hosted 러너 v2.327.1 이상을 요구합니다.
