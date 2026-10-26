# DATA_MODEL: Todo 앱 (초안)

- 상태: 초안
- 근거 문서: `docs/PRD.md` (기술 스택은 `docs/TRD.md`: MySQL + Drizzle)
- 테이블은 최소한으로, MVP(F-01~F-05)에 필요한 것만 둔다.

## 1. 테이블 목록

| 테이블 | 용도 |
|------|------|
| todos | 할 일 한 건을 한 행으로 저장한다. |

사용자 테이블은 없다. 로그인이 범위 밖이고 혼자 쓰는 앱이기 때문이다. 카테고리, 마감일도 범위 밖이라 필드를 만들지 않는다.

## 2. todos 테이블

| 필드 | 타입 (MySQL) | 제약조건 | 설명 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT, NOT NULL | 할 일을 구분하는 번호. 삭제(F-04)와 완료 전환(F-03) 때 대상을 찾는 데 쓴다. |
| title | VARCHAR(100) | NOT NULL, 길이 1~100자 (CHECK) | 할 일 제목 (F-01). 빈 제목은 허용하지 않는다. |
| completed | BOOLEAN (내부적으로 TINYINT(1)) | NOT NULL, 기본값 false | 완료 여부 (F-03). 새 할 일은 미완료로 시작한다. |
| created_at | TIMESTAMP(3) | NOT NULL, 기본값 CURRENT_TIMESTAMP(3) | 만든 시각. 목록을 최신순으로 정렬(F-02)하는 기준이다. |

### 제약조건 설명

- **제목 길이:** 1~100자 규칙은 Zod(화면, 서버)와 DB(길이 제한, 빈 값 금지) 양쪽에서 지킨다. 어느 한쪽이 뚫려도 잘못된 데이터가 저장되지 않게 하기 위해서다.
- **MySQL 주의점:** CHECK 제약은 MySQL 8.0.16 이상에서만 실제로 적용된다. 그보다 낮은 버전이면 무시되므로 Zod 검증이 유일한 방어선이 된다. BOOLEAN은 0/1 숫자로 저장되지만 Drizzle이 true/false로 바꿔준다.
- **정렬:** 목록은 `created_at` 내림차순으로 읽는다. 같은 시각에 만들어진 경우를 대비해 `id` 내림차순을 보조 기준으로 쓴다.
- **삭제:** 행을 실제로 지운다. 삭제한 항목은 복구하지 않는다는 PRD 규칙을 따른다.
- **수정 시각 없음:** 제목 수정은 v0.4 이후 기능이라 `updated_at`은 만들지 않는다. 그때 필요하면 추가한다.

## 3. TypeScript 타입 예시

위치는 `src/types/`를 가정한다. 화면과 서버가 같은 타입을 공유한다.

```ts
// 할 일 한 건 (DB에서 읽어온 모습)
export type Todo = {
  id: number;
  title: string; // 1~100자
  completed: boolean;
  createdAt: string; // API로 주고받을 때는 날짜 문자열(ISO 8601)
};

// 할 일 추가 요청 (F-01): 제목만 받는다
export type CreateTodoInput = {
  title: string;
};

// 완료 상태 변경 요청 (F-03)
export type UpdateTodoCompletedInput = {
  completed: boolean;
};
```

- `id`, `completed`, `createdAt`은 사용자가 정하지 않고 서버와 DB가 채운다. 그래서 추가 요청에는 `title`만 있다.
- 필드 이름은 TypeScript에서는 `createdAt`(camelCase), DB 컬럼은 `created_at`(snake_case)으로 쓴다. 변환은 Drizzle 쪽에서 맞춘다.

## 4. 기능과 데이터 대응

| 기능 | 하는 일 |
|------|------|
| F-01 추가 | todos에 새 행 저장 (title만 입력, 나머지는 기본값) |
| F-02 목록 | todos 전체를 created_at 내림차순으로 조회 |
| F-03 완료 전환 | id로 찾은 행의 completed 값 변경 |
| F-04 삭제 | id로 찾은 행 삭제 |
| F-05 유지 | DB에 저장하므로 새로고침해도 유지 (v0.3부터) |

## 5. 확인이 필요한 항목

- id 형태: 이 문서는 구분하기 쉬운 정수 자동 증가를 가정했다. 필요하면 UUID로 바꿀 수 있다 (TRD의 미결정 항목).
- MySQL 버전: CHECK 제약을 쓰려면 8.0.16 이상이어야 한다 (TRD의 미결정 항목).
- 제목 공백 처리: 앞뒤 공백을 제거한 뒤 길이를 셀지 (PRD의 미결정 항목).
