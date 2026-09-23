# CI/CD 상세

## 검사 내용

### kwak-service-fe (`ci-frontend.yml`)

검사 3개가 **각각 별도 job** 입니다. PR 체크 목록에 셋이 따로 뜨므로 어느 검사가
깨졌는지 바로 보이고, 병렬로 돕니다.

| job | 표시 이름 | 명령 | 비고 |
|---|---|---|---|
| `lint` | ESLint | `npm run lint` | eslint 9 flat config |
| `typecheck` | 타입체크 | `npm run typecheck` | `tsc --noEmit`. vite 빌드는 타입을 안 본다 |
| `build` | 빌드 | `npm run build` | 배포가 Dockerfile 안에서 도는 그 빌드 |

서로 `needs` 로 묶지 않았습니다. lint 가 깨져도 빌드 결과를 같이 보는 편이
진단에 낫기 때문입니다.

셋은 겹치지 않고 각자 다른 층을 봅니다 — ESLint 는 소스를 텍스트로(파일 단위),
tsc 는 타입을 계산해(프로젝트 전체), 빌드는 실제 번들을 만들어서. 실제로
`vite.config.ts` 부재는 앞의 둘을 통과하고 빌드에서만 걸렸습니다.

대신 job 마다 `npm ci` 를 따로 돌립니다. npm 캐시를 공유해 실제 비용은 작고,
public 레포라 Actions 시간도 무제한입니다.

`react-refresh/only-export-components`와 `react-hooks/exhaustive-deps`는 경고로
두었습니다(현재 21건). 에러는 0건이어야 통과합니다.

### kwak-service-fe E2E (`e2e-frontend.yml`) — 수동 실행

Playwright 스모크 5개. `npm run preview` 로 빌드 산출물(dist)을 띄우고 실제
Chromium 에서 확인하므로, ESLint·타입체크가 잡지 못하는 라우팅 깨짐과 런타임
크래시를 잡습니다.

| 테스트 | 검증하는 것 |
|---|---|
| `/resume` 렌더 | 인증 불필요 화면 + 콘솔 에러 없음 |
| 상단 탭 이동 | `/resume/career`, `/resume/portfolio` 라우팅 |
| `/login` 렌더 | 콘솔 에러 없음 |
| `/` → `/login` | 쿠키 없을 때 `ProtectedRoute` 리다이렉트 |
| 없는 경로 | `path: "*"` → `ErrorPage` |

**백엔드를 띄우지 않습니다.** 쿠키가 없으면 `AuthContext` 가 API 를 호출하지
않고 `isLoggedIn=false` 로 끝나기 때문에 위 항목들은 결정적으로 재현됩니다.

로그인 이후 화면을 검증하려면 백엔드가 필요하고, `kwak-service-be` 에
Dockerfile 이 없어 현재는 CI 에서 띄울 수 없습니다.

주의: 상단 탭의 세 번째 라벨은 "사이드 프로젝트"인데 경로는
`/resume/portfolio` 입니다. 라벨과 경로가 다릅니다.

### kwak-service-be (`ci-backend.yml`)

검사 2개가 **각각 별도 job** 입니다.

| job | 표시 이름 | 명령 | 서비스 컨테이너 |
|---|---|---|---|
| `migrations` | 마이그레이션 규칙 | `check-migrations.py` | 없음 |
| `build-test` | 빌드 + 테스트 | `./gradlew build` | MySQL + Redis |

마이그레이션 검사는 DB 도 JDK 도 필요 없어서 서비스 컨테이너 기동(~30초)을
기다리지 않습니다. V 번호 중복 같은 실수를 빌드 3분 뒤에 알 이유가 없어
따로 뺐습니다.

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
| 테스트 | `pytest -q` | 17개 |

**Ruff 는 넣지 않았습니다.** 한 번 도입해서 57건(설정 기준) 을 고쳤다가
되돌렸습니다. 기본 룰셋으로는 190건이 넘습니다. 린트를 붙이려면 소스를 전면
정리해야 하는데, 그 정리를 하지 않기로 했기 때문입니다.

나중에 도입한다면 `--select F` (미사용 import·변수, 미정의 이름) 처럼 좁은
룰셋부터 시작하고, `E501`(줄 길이)은 빼는 편이 현실적입니다.

`test_pipeline.py`와 `test_stock_scheduler.py`는 테스트가 아니라 **진단 스크립트**입니다.
모듈 최상위에서 바로 실행되도록 작성돼 있어 import만으로 실제 DB·LLM·외부 네트워크를
때립니다. `pyproject.toml`에서 pytest 수집 대상에서 제외했습니다.

## 배포는 자동화하지 않는다

배포 워크플로는 넣지 않았습니다. 서버에서 직접 합니다.
과거 시도와 그때 드러난 사실을 남겨 둡니다.

### self-hosted 러너는 한 번도 동작한 적이 없다

기존 `deploy.yml` 의 실행 이력:

- `kwak-service-fe` — `Deploy Frontend` 18회 전부 `cancelled`
- `kwak-service-be` — `Deploy Backend` 29회 전부 `cancelled`

모두 `created_at` 과 `updated_at` 간격이 정확히 24시간입니다. GitHub 이 러너를
못 잡은 job 을 24시간 뒤 자동 취소한 것으로, 레포 첫 커밋(2026-06-22)부터
`self-hosted` 라벨 러너가 job 을 가져간 적이 없습니다. 운영 컨테이너는 서버에서
수동으로 띄운 것으로 보입니다.

### 나중에 배포를 자동화한다면

1. **public 레포 + self-hosted 러너는 위험합니다.** fork PR 이 러너에서 외부 코드를
   실행할 수 있습니다. 워크플로 조건만으로는 못 막습니다 — `pull_request` 이벤트는
   PR 브랜치의 워크플로 파일을 쓰므로, 공격자가 자기 fork 에서 `runs-on: self-hosted`
   를 써넣으면 우회됩니다.
   현재 fe/be 는 **PR 생성이 `collaborators_only`** 로 잠겨 있어 외부인이 PR 자체를
   열 수 없습니다. 이 설정을 풀면서 self-hosted 러너를 붙이면 안 됩니다.
2. **`kwak-service-be` 에는 `docker-compose.yml` 과 각 서비스 `Dockerfile` 이
   없습니다.** gitignore 에 있는 것도 아니고 그냥 존재하지 않습니다. 러너 작업공간에
   수동으로 두는 것으로는 해결되지 않습니다 — `actions/checkout` 은 `clean` 입력이
   기본 `true` 라 job 시작 시 `git clean -ffdx` 로 작업공간을 비웁니다.
3. `collector` 의 compose 는 `env_file: .env` 를 요구합니다. `.env` 는 커밋할 수
   없으므로 Secrets 에서 생성하는 단계가 필요합니다.
4. 러너는 `--ephemeral` 로 등록하고, root 가 아닌 계정으로, 운영 호스트와 분리된
   곳에 두는 편이 좋습니다.

## 검증 상태

세 레포의 검사 워크플로는 모두 GitHub Actions 에서 실제로 돌려 통과를 확인했습니다
(fe 38초, collector 35초, be 2분 46초). be 는 MySQL·Redis 서비스 컨테이너로
`PortalApplicationTests` 의 컨텍스트 기동까지 확인됐습니다.

다만 워크플로에 나중에 추가한 `permissions` 와 `persist-credentials: false` 는
actionlint 까지만 확인했고 실제 실행 검증은 다음 push 에서 이뤄집니다.

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
