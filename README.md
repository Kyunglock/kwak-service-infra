# kwak-service-infra

곽 서비스의 CI/CD를 모아두는 레포입니다. 검사와 배포 로직이 여기 한 곳에 있고,
각 서비스 레포는 3~5줄짜리 호출 파일만 가집니다.

## 구성

```
.github/workflows/
  ci-frontend.yml      # kwak-service-fe  — ESLint / 타입체크 / 빌드
  ci-backend.yml       # kwak-service-be  — Gradle 빌드+테스트 / 마이그레이션 규칙
  ci-collector.yml     # collector        — Ruff / pytest
  deploy-frontend.yml  # docker build + run
  deploy-compose.yml   # docker compose (be, collector 공용)
scripts/
  check-migrations.py  # V*.sql 번호 중복·명명 규칙 검사
docs/
  CI-CD.md             # 상세 문서
```

## 서비스 레포에서 쓰는 법

각 레포의 `.github/workflows/ci.yml`:

```yaml
jobs:
  ci:
    uses: Kyunglock/kwak-service-infra/.github/workflows/ci-frontend.yml@main
  deploy:
    needs: ci
    if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'
    uses: Kyunglock/kwak-service-infra/.github/workflows/deploy-frontend.yml@main
```

재사용 워크플로 안의 `actions/checkout`은 **호출한 레포의 해당 커밋**을 받아옵니다.
그래서 별도 토큰 없이 동작합니다.

## 러너 배치 원칙

| 종류 | 러너 | 트리거 |
|---|---|---|
| 검사 | `ubuntu-latest` | PR + main push |
| 배포 | `self-hosted` | main push / 수동 실행만 |

`kwak-service-fe`와 `kwak-service-be`는 **public 레포**입니다. public 레포에서
fork PR이 self-hosted 러너에 닿으면 남의 코드가 배포 서버에서 실행됩니다.
그래서 **검사는 절대 self-hosted에서 돌리지 않고**, 배포 job은 PR에서 실행되지
않도록 트리거를 좁게 잡습니다. 이 원칙을 깨는 변경은 넣지 마세요.

## ⚠️ self-hosted 러너가 아직 없습니다

배포 job 은 `self-hosted` 러너를 요구하는데, 현재 등록된 러너가 없습니다.
fe 18회 / be 29회의 기존 배포 실행이 전부 24시간 대기 후 자동 취소됐습니다 —
**배포 자동화는 한 번도 동작한 적이 없습니다.** 자세한 내용은 `docs/CI-CD.md` 참고.

검사(ubuntu-latest)는 정상 동작합니다.

## 주의: 이 레포는 public 입니다

실제 비밀값은 여기 두지 말고 GitHub Secrets를 쓰세요. 워크플로 로그도 공개됩니다.
