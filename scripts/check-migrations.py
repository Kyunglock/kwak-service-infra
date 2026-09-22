#!/usr/bin/env python3
"""DB 마이그레이션 SQL 파일의 명명/번호 규칙을 검사한다.

kwak-service-be 는 Flyway 를 쓰지 않고 `db/migration/V*.sql` 을 수동 실행한다
(ARCHITECTURE.md 참고). 도구가 순서를 강제해 주지 않으므로, 최소한 파일 이름과
버전 번호만이라도 CI 에서 지킨다.

에러(빌드 실패):
  - Flyway 규칙(V<번호>__<설명>.sql)을 벗어난 파일명
  - 같은 버전 번호를 쓰는 파일이 둘 이상  <- 병합 시 제일 흔한 사고
경고(실패시키지 않음):
  - 버전 번호에 빈 구간이 있음 (파일을 지웠거나 아직 머지 안 된 브랜치가 있을 수 있음)

사용법: check-migrations.py <검색 시작 디렉터리>
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

PATTERN = re.compile(r"^V(\d+)__[A-Za-z0-9_]+\.sql$")


def main(root: Path) -> int:
    files = sorted(root.rglob("db/migration/*.sql"))
    if not files:
        print(f"::warning::{root} 아래에서 마이그레이션 파일을 찾지 못했습니다.")
        return 0

    errors = 0
    by_version: dict[int, list[Path]] = defaultdict(list)

    for path in files:
        match = PATTERN.match(path.name)
        if not match:
            print(
                f"::error file={path}::파일명이 V<번호>__<설명>.sql 규칙에 맞지 않습니다: {path.name}"
            )
            errors += 1
            continue
        by_version[int(match.group(1))].append(path)

    for version, paths in sorted(by_version.items()):
        if len(paths) > 1:
            joined = ", ".join(str(p) for p in paths)
            print(f"::error::V{version} 을 쓰는 파일이 {len(paths)}개입니다: {joined}")
            errors += 1

    if by_version:
        versions = sorted(by_version)
        missing = [v for v in range(versions[0], versions[-1] + 1) if v not in by_version]
        if missing:
            print(f"::warning::버전 번호가 비어 있는 구간: {missing}")
        print(f"마이그레이션 {len(files)}개, 버전 V{versions[0]}~V{versions[-1]} 확인")

    if errors:
        print(f"::error::마이그레이션 검사 실패 — 에러 {errors}건")
        return 1

    print("마이그레이션 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
