# CI 흐름

레포별로 무엇이 언제 어떻게 도는지 정리한 문서입니다.
검사를 왜 그렇게 골랐는지, 알려진 문제와 미룬 것들은 `CI-CD.md` 를 보세요.

## 전체 구조

검사 로직은 이 레포(infra)에 있고, 각 서비스 레포는 호출만 합니다.

```
kwak-service-fe/.github/workflows/ci.yml          ─┐
kwak-service-be/.github/workflows/ci.yml          ─┼─> kwak-service-infra
collector/.github/workflows/ci.yml                ─┘     .github/workflows/ci-*.yml
```

재사용 워크플로 안의 `actions/checkout` 은 **호출한 레포의 해당 커밋**을 받아옵니다.
그래서 별도 토큰 없이 동작합니다. infra 가 public 이라 private 인 collector 에서도
호출됩니다(private → public 방향은 막히지 않습니다).

검사 내용을 바꾸려면 **infra 쪽 `ci-*.yml` 을 고칩니다.** 서비스 레포의 `ci.yml` 은
3줄짜리 호출 파일이라 건드릴 일이 거의 없습니다.

## 언제 도는가

세 레포 모두 같습니다.

| 이벤트 | 검사 |
|---|---|
| PR 열림 / PR 에 push | 돈다 |
| main 에 push | 돈다 |
| 기능 브랜치에 push (PR 없음) | **안 돈다** |
| Actions 탭 → Run workflow | 돈다 |

기능 브랜치만 밀어두면 아무것도 돌지 않습니다. PR 을 열어야 검사가 시작됩니다.

러너는 전부 `ubuntu-latest`(GitHub 호스팅)입니다. `self-hosted` 는 쓰지 않습니다 —
fe/be 가 public 레포라 fork PR 이 self-hosted 러너에 닿으면 외부 코드가 서버에서
실행될 수 있기 때문입니다.

---

## kwak-service-fe

검사 3개가 **각각 별도 job** 이라 PR 체크 목록에 셋이 따로 뜨고 병렬로 돕니다.

```
PR / main push
   ├─ ci / ESLint    ── checkout → node 20 → npm ci → npm run lint       ~27초
   ├─ ci / 타입체크    ── checkout → node 20 → npm ci → npm run typecheck  ~28초
   └─ ci / 빌드       ── checkout → node 20 → npm ci → npm run build      ~28초
```

서로 `needs` 로 묶지 않았습니다. lint 가 깨져도 빌드 결과를 같이 보는 편이 진단에
낫기 때문입니다. job 마다 `npm ci` 를 다시 돌지만 npm 캐시를 공유해 비용은 작습니다.

**셋은 겹치지 않고 각자 다른 층을 봅니다.**

| 검사 | 보는 것 | 범위 |
|---|---|---|
| ESLint | 소스를 텍스트로 훑음 | 파일 단위 |
| `tsc --noEmit` | 타입을 계산해 맞춰봄 | 프로젝트 전체 |
| `vite build` | 실제 번들을 만들어냄 | 런타임 직전 |

뒤가 앞을 대신하지 못합니다. vite 빌드는 타입을 검사하지 않아서 타입 에러가 있어도
빌드는 성공합니다. 앞도 뒤를 대신하지 못합니다 — `vite.config.ts` 가 없어 alias 가
안 풀리던 문제는 ESLint·tsc 를 통과하고 빌드에서만 걸렸습니다.

타입체크 범위에는 `src` 와 `e2e` 가 들어갑니다. Playwright 는 스펙 파일을 타입 검사
없이 트랜스파일만 하므로, `e2e` 를 빼두면 테스트 코드의 타입 오류가 실행 전까지
드러나지 않습니다.

---

## kwak-service-be

검사 2개가 별도 job 입니다.

```
PR / main push
   ├─ ci / 마이그레이션 규칙  ── checkout → infra checkout → 스크립트         ~5초
   └─ ci / 빌드 + 테스트     ── MySQL·Redis 기동 → checkout → JDK 21
                               → Gradle → ./gradlew build                ~151초
```

마이그레이션 검사를 떼어낸 이유는 **DB 도 JDK 도 필요 없기 때문**입니다. 한 job 에
묶여 있을 때는 서비스 컨테이너 기동(~30초)과 Gradle 빌드(~2분)를 다 기다린 뒤에야
결과가 나왔습니다. V 번호 중복 같은 실수를 3분 뒤에 알 이유가 없습니다.

### 마이그레이션 규칙 (`scripts/check-migrations.py`)

BE 는 Flyway 를 쓰지 않고 `db/migration/V*.sql` 을 **수동 실행**합니다. 도구가
순서를 강제해 주지 않으므로 파일명과 번호만이라도 CI 에서 지킵니다.

- 에러: 파일명이 `V<번호>__<설명>.sql` 규칙을 벗어남
- 에러: 같은 버전 번호를 쓰는 파일이 둘 이상 (병합 시 제일 흔한 사고)
- 경고(실패 아님): 번호에 빈 구간이 있음

스크립트는 infra 에 있어서, 이 job 은 레포를 **둘** 체크아웃합니다 — BE 를 작업
디렉터리에, infra 를 `.infra/` 에.

### 빌드 + 테스트

`./gradlew build` 로 컴파일 + 테스트 170개(31파일)를 돌립니다.

서비스 컨테이너로 **MySQL 8.0 + Redis 7** 을 띄웁니다. 테스트 중 `@SpringBootTest`
는 `PortalApplicationTests` 하나뿐이고 나머지는 전부 Mockito 단위 테스트인데,
그 하나가 전체 컨텍스트를 띄우고 HikariCP 가 기동 시 커넥션을 만들기 때문입니다.
Flyway 를 쓰지 않으므로 빈 스키마로 충분합니다.

`application.yml` / `application-local.yml` 의 placeholder 에는 기본값이 없어
하나라도 비면 컨텍스트가 뜨지 않습니다. 그래서 더미 환경변수 14개를 주입합니다
(`JWT_SECRET`, `DB_URL`, `KAKAO_CLIENT_ID` 등). 실제 값이 아니므로 외부 연동을
타는 코드는 CI 에서 실패하는 게 정상이고, 현재 테스트는 그 경로를 타지 않습니다.

테스트 리포트는 실패해도 항상 아티팩트로 올라갑니다(7일 보관).

---

## collector

검사가 하나라 job 도 하나입니다.

```
PR / main push
   └─ ci / check  ── checkout → python 3.11 → pip install → pytest -q   ~35초
```

`requirements-dev.txt` 가 `requirements.txt` 를 포함합니다. 테스트가
`api_internal`(fastapi) 를 import 하므로 런타임 의존성도 필요합니다.

**`test_pipeline.py` 와 `test_stock_scheduler.py` 는 테스트가 아니라 진단
스크립트입니다.** 모듈 최상위에서 바로 실행되도록 작성돼 있어 import 만으로 실제
DB·LLM·외부 네트워크를 때립니다. `pyproject.toml` 에서 수집 대상에서 제외했습니다.

Ruff 는 넣지 않았습니다. 이유는 `CI-CD.md` 참고.

---

## 수동 실행: fe E2E (Playwright)

`workflow_dispatch` 전용입니다. **Actions 탭 → E2E → Run workflow.**

```
수동 실행
   └─ e2e  ── checkout → node 20 → npm ci → chromium 설치
              → npm run test:e2e (vite preview 가 dist 를 4173 에 띄움)
```

게이트가 아닙니다. 브라우저를 띄우느라 느리고, 매 push 마다 돌릴 만큼 자주 깨지는
영역도 아니라서 이렇게 두었습니다.

**백엔드를 띄우지 않습니다.** 쿠키가 없으면 `AuthContext` 가 API 를 호출하지 않고
`isLoggedIn=false` 로 끝나므로, 인증이 필요 없는 화면과 리다이렉트·에러 처리는
백엔드 없이 결정적으로 재현됩니다. 실측으로 확인했습니다 — 테스트 중 나가는 요청은
HTML·JS·CSS 뿐이고 API 호출은 0건입니다.

| 테스트 | 검증하는 것 |
|---|---|
| `/resume` 렌더 | 인증 불필요 화면 + 콘솔 에러 없음 |
| 상단 탭 이동 | `/resume/career`, `/resume/portfolio` 라우팅 |
| `/login` 렌더 | 콘솔 에러 없음 |
| `/` → `/login` | 쿠키 없을 때 `ProtectedRoute` 리다이렉트 |
| 없는 경로 | `path: "*"` → `ErrorPage` |

잡는 것은 라우팅 깨짐, 런타임 크래시, 번들 문제입니다. **못 잡는 것**은 로그인 이후
화면 전부, API 계약, FE↔BE 연동입니다. "앱이 켜지고 페이지가 그려지는가" 수준의
스모크입니다.

주의: 상단 탭 세 번째 라벨은 "사이드 프로젝트"인데 경로는 `/resume/portfolio` 입니다.
셀렉터를 경로로 짐작하면 안 됩니다.

---

## 실패하면 어디를 보나

1. PR 체크 목록에서 **어느 job 이 빨간지** 확인 (그래서 job 을 나눠 두었습니다)
2. 그 job 의 Actions 로그
3. BE 테스트 실패면 `test-reports` 아티팩트(HTML)를 받아서 확인

## 검사를 바꾸려면

| 하고 싶은 것 | 고칠 곳 |
|---|---|
| 검사 추가·제거·명령 변경 | infra `.github/workflows/ci-*.yml` |
| 호출하는 워크플로 자체를 바꿈 | 각 레포 `.github/workflows/ci.yml` |
| 마이그레이션 규칙 | infra `scripts/check-migrations.py` |
| lint 규칙 | fe `eslint.config.js` |
| 타입체크 범위 | fe `tsconfig.json` 의 `include` |
| pytest 수집 범위 | collector `pyproject.toml` |

서비스 레포가 `@main` 으로 호출하므로 **infra 변경은 즉시 반영됩니다.** 안정성이
필요해지면 태그를 끊어 `@v1` 형태로 고정하세요.

## 배포

**자동화하지 않습니다. 서버에서 직접 합니다.** 경위와 주의사항은 `CI-CD.md` 참고.

## main 보호 (예정)

모든 변경을 PR 로 거치게 하려면 ruleset 이 필요합니다. **아직 걸려 있지 않습니다** —
지금은 CI 가 빨개도 머지되고 main 직접 push 도 됩니다.

걸 때 넣을 규칙:

| 규칙 | 효과 |
|---|---|
| `pull_request` | main 직접 push 차단 (승인 수는 **0** — 개인 레포는 자기 PR 을 승인할 수 없다) |
| `required_status_checks` | CI 초록이어야 머지 가능 |
| `non_fast_forward` | force push 차단 |
| `deletion` | main 삭제 차단 |

등록할 체크 이름은 띄어쓰기까지 정확해야 합니다. 오타가 있으면 그 검사는 영원히
pending 으로 남아 머지가 막힙니다.

| 레포 | 체크 이름 |
|---|---|
| kwak-service-fe | `ci / ESLint`, `ci / 타입체크`, `ci / 빌드` |
| kwak-service-be | `ci / 마이그레이션 규칙`, `ci / 빌드 + 테스트` |
| collector | `ci / check` |

infra 에는 CI 워크플로가 없습니다(전부 `workflow_call` 전용이라 자기 레포에선 실행되지
않음). 그래서 `required_status_checks` 를 걸 대상이 없습니다.
