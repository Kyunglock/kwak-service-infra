# kwak-service-infra

곽 서비스의 **CI 검사**를 모아두는 레포입니다. 검사 로직이 여기 한 곳에 있고,
각 서비스 레포는 3줄짜리 호출 파일만 가집니다.

**배포는 자동화하지 않습니다.** 서버에서 직접 합니다.

## 구성

```
.github/workflows/
  lint-workflows.yml   # 이 레포 자신     — actionlint                 (PR·push 자동)
  ci-frontend.yml      # kwak-service-fe  — ESLint / 타입체크 / 빌드   (재사용, PR·push 자동)
  ci-backend.yml       # kwak-service-be  — Gradle 빌드+테스트 / 마이그레이션 규칙 (재사용)
  ci-collector.yml     # collector        — pytest                    (재사용)
  e2e-frontend.yml     # kwak-service-fe  — Playwright 스모크          (재사용, 수동 실행)
scripts/
  check-migrations.py  # V*.sql 번호 중복·명명 규칙 검사
docs/
  CI-FLOW.md           # 레포별 CI 흐름 — 무엇이 언제 어떻게 도는가
  CI-CD.md             # 결정 기록 — 왜 그렇게 정했나, 알려진 문제
```

## 서비스 레포에서 쓰는 법

각 레포의 `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  ci:
    uses: Kyunglock/kwak-service-infra/.github/workflows/ci-frontend.yml@main
```

재사용 워크플로 안의 `actions/checkout`은 **호출한 레포의 해당 커밋**을 받아옵니다.
그래서 별도 토큰 없이 동작합니다.

## 수동 실행 워크플로

`e2e-frontend.yml` 은 게이트가 아닙니다. fe 의 `e2e.yml` 이 `workflow_dispatch`
로만 걸려 있어, Actions 탭 → E2E → Run workflow 로만 돕니다.

브라우저를 띄우느라 평소 검사보다 느리고, 매 push 마다 돌릴 만큼 자주 깨지는
영역도 아니라서 이렇게 두었습니다.

## 원칙

- 검사는 전부 **`ubuntu-latest`** (GitHub 호스팅)에서 돕니다.
- **`self-hosted` 러너는 쓰지 않습니다.** `kwak-service-fe`와 `kwak-service-be`가
  public 레포라, self-hosted 러너를 붙이면 fork PR 을 통해 외부 코드가 서버에서
  실행될 수 있습니다. 배포를 자동화하게 되면 `docs/CI-CD.md` 의 해당 항목을
  먼저 읽으세요.
- 워크플로는 `permissions: contents: read` 와 `persist-credentials: false` 를
  명시합니다. 검사는 커밋·이슈·패키지를 건드릴 일이 없습니다.

## 주의: 이 레포는 public 입니다

실제 비밀값은 여기 두지 말고 GitHub Secrets를 쓰세요. 워크플로 로그도 공개됩니다.
