# self-hosted 러너 보안 체크리스트

`kwak-service-fe` 와 `kwak-service-be` 는 **public 레포**입니다. GitHub 이
self-hosted 러너를 붙일 때 경고를 띄우는 조합입니다:

> Using self-hosted runners in public repositories is not recommended.
> Forks of your public repository can potentially run dangerous code on your
> self-hosted runner by creating a pull request.

누구나 fork 해서 PR 을 열 수 있고, 그 PR 이 러너에서 실행되면 남의 코드가
배포 서버에서 돕니다.

## 워크플로 조건만으로는 못 막는다

현재 `deploy` job 은 `github.event_name == 'workflow_dispatch'` 로 막혀 있어
fork PR 로는 돌지 않습니다. **하지만 이것만 믿으면 안 됩니다.**

`pull_request` 이벤트에서 GitHub 은 **PR 브랜치에 들어 있는 워크플로 파일**을
사용합니다. 공격자는 자기 fork 에서 `ci.yml` 을 고쳐 `runs-on: self-hosted` 를
직접 써넣고 가드를 지운 PR 을 열 수 있습니다. 이 레포의 워크플로를 아무리
잠가도 그 경로는 막히지 않습니다.

막아 주는 것은 **레포 설정**입니다.

## 러너를 붙이기 전에 해야 할 설정

레포마다 따로 해야 합니다 (`kwak-service-fe`, `kwak-service-be`).

### 1. fork PR 승인 — 가장 중요

**Settings → Actions → General → Fork pull request workflows from outside collaborators**

- 기본값 `Require approval for first-time contributors`
  — PR 이 한 번 머지된 사람은 이후 자동 실행됩니다
- **`Require approval for all external collaborators` 로 바꿀 것**
  — 모든 fork PR 이 승인을 거칩니다

public 레포에 self-hosted 러너를 붙인다면 이 한 줄이 제일 중요합니다.

### 2. GITHUB_TOKEN 기본 권한

**Settings → Actions → General → Workflow permissions**

- `Read repository contents and packages permissions` 선택
- 이 레포의 워크플로는 모두 `permissions: contents: read` 를 명시하고 있어
  토큰을 더 달라고 하지 않습니다.

### 3. 러너 자체

- **`--ephemeral` 로 등록**할 것. job 하나 돌고 러너가 폐기되므로 작업공간이
  다음 job 으로 새지 않습니다.
- 운영 컨테이너를 돌리는 호스트와 **분리된 VM/컨테이너**에 두는 편이 좋습니다.
- **root 로 돌리지 말 것.**
- 러너 버전은 v2.327.1 이상 (`actions/checkout@v7` 요구사항).

### 4. 쓰지 말 것

- `pull_request_target` — fork 코드를 신뢰 컨텍스트에서 돌립니다.
  현재 워크플로에는 없습니다.
- 검사(lint/test/build)를 `self-hosted` 로 옮기는 것.
  검사는 전부 `ubuntu-latest` 에 두는 게 이 구조의 전제입니다.

## 더 간단한 길

**`kwak-service-fe` 와 `kwak-service-be` 를 private 으로 내리면** 이 경고와
fork PR 벡터가 통째로 사라집니다.

`kwak-service-infra` 만 public 이면 재사용 워크플로 호출에는 충분합니다.
private 레포가 public 레포의 워크플로를 호출하는 방향은 막히지 않기 때문입니다.
infra 에는 러너가 붙지 않고 호출당하는 워크플로 정의만 있습니다.

권장 조합: **infra 만 public, 나머지 셋 private.**

## 참고: 작업공간에 파일을 수동으로 두지 말 것

`actions/checkout` 은 `clean` 입력이 기본 `true` 라 `git clean -ffdx` 를
먼저 돌립니다. 러너 작업공간에 손으로 만들어 둔 파일은 job 시작 시 지워집니다.
배포에 필요한 파일(`docker-compose.yml`, `Dockerfile`, `vite.config.ts` 등)은
반드시 레포에 커밋되어 있어야 합니다. `.env` 처럼 커밋할 수 없는 값은
GitHub Secrets 나 러너 외부 경로를 쓰세요.
