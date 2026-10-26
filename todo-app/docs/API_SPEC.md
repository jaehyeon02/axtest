# API_SPEC: Todo 앱 (초안)

- 상태: 초안
- 근거 문서: `docs/DATA_MODEL.md` (`docs/PRD.md`의 F-01~F-04 대응)
- 위치: `app/api/` 아래 API 라우트
- 요청/응답 본문은 모두 JSON이다. 요청 본문이 있으면 `Content-Type: application/json`을 쓴다.
- 입력 검증은 Zod로 하며, 화면과 서버가 같은 규칙을 쓴다.

## 1. 공통 규칙

### 할 일 객체 (Todo)

`DATA_MODEL.md`의 `Todo` 타입과 같다.

| 필드 | 타입 | 설명 |
|------|------|------|
| id | number | 할 일 번호 |
| title | string | 제목 (1~100자) |
| completed | boolean | 완료 여부 |
| createdAt | string | 만든 시각 (ISO 8601, 예: `2026-10-23T09:30:00.123Z`) |

### 에러 형식

모든 에러 응답은 다음 형식으로 통일한다.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "제목은 1~100자로 입력해 주세요."
  }
}
```

- `code`: 프로그램이 구분하는 고정 문자열(영문 대문자 + 밑줄)
- `message`: 사용자에게 보여줄 수 있는 한국어 안내 문구

### 에러 코드 목록

| code | 상태 코드 | 의미 |
|------|------|------|
| INVALID_JSON | 400 | 요청 본문이 올바른 JSON이 아니다. |
| VALIDATION_ERROR | 400 | 요청 값이 규칙에 맞지 않는다. (제목 누락, 1~100자 위반, completed가 boolean이 아님 등) |
| INVALID_ID | 400 | 주소의 id가 양의 정수가 아니다. |
| NOT_FOUND | 404 | 해당 id의 할 일이 없다. |
| INTERNAL_ERROR | 500 | 서버 또는 DB 오류. 내부 오류 내용은 응답에 담지 않는다. |

## 2. 엔드포인트 목록

| 기능 | 메서드 | 경로 | 성공 상태 코드 |
|------|------|------|------|
| F-02 목록 보기 | GET | `/api/todos` | 200 |
| F-01 추가 | POST | `/api/todos` | 201 |
| F-03 완료 전환 | PATCH | `/api/todos/{id}` | 200 |
| F-04 삭제 | DELETE | `/api/todos/{id}` | 204 |

F-05(데이터 유지)는 별도 API 없이, 위 API들이 DB에 저장하고 읽어오는 것으로 충족한다.

## 3. GET /api/todos (F-02 목록 보기)

할 일 전체를 최신순(`createdAt` 내림차순, 같으면 `id` 내림차순)으로 돌려준다.

- 요청: 본문 없음

### 성공 응답: 200 OK

```json
{
  "todos": [
    {
      "id": 2,
      "title": "우유 사기",
      "completed": false,
      "createdAt": "2026-10-23T09:31:10.000Z"
    },
    {
      "id": 1,
      "title": "PRD 읽기",
      "completed": true,
      "createdAt": "2026-10-23T09:30:00.000Z"
    }
  ]
}
```

할 일이 하나도 없으면 `{ "todos": [] }`를 돌려준다. 에러가 아니다.

### 에러

| 상황 | 상태 코드 | code |
|------|------|------|
| DB 오류 등 서버 문제 | 500 | INTERNAL_ERROR |

## 4. POST /api/todos (F-01 추가)

새 할 일을 만든다. `completed`는 `false`로 시작한다.

### 요청

| 필드 | 타입 | 필수 | 규칙 |
|------|------|------|------|
| title | string | 예 | 1~100자 |

```json
{
  "title": "우유 사기"
}
```

### 성공 응답: 201 Created

```json
{
  "todo": {
    "id": 3,
    "title": "우유 사기",
    "completed": false,
    "createdAt": "2026-10-23T09:32:00.000Z"
  }
}
```

### 에러

| 상황 | 상태 코드 | code | message 예시 |
|------|------|------|------|
| 본문이 JSON이 아님 | 400 | INVALID_JSON | 요청 형식이 올바르지 않습니다. |
| title 없음, 문자열이 아님, 빈 문자열 | 400 | VALIDATION_ERROR | 제목을 입력해 주세요. |
| title이 100자 초과 | 400 | VALIDATION_ERROR | 제목은 100자 이하로 입력해 주세요. |
| DB 오류 등 서버 문제 | 500 | INTERNAL_ERROR | 서버에 문제가 생겼습니다. 잠시 후 다시 시도해 주세요. |

에러 예시 (제목이 비어 있을 때):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "제목을 입력해 주세요."
  }
}
```

## 5. PATCH /api/todos/{id} (F-03 완료 전환)

할 일의 완료 여부를 바꾼다. 현재 값을 뒤집는 방식이 아니라, 원하는 값을 직접 보낸다. 같은 요청을 두 번 보내도 결과가 같다.

### 요청

- 경로 변수: `id` (양의 정수)

| 필드 | 타입 | 필수 | 규칙 |
|------|------|------|------|
| completed | boolean | 예 | `true` 또는 `false` |

```json
{
  "completed": true
}
```

### 성공 응답: 200 OK

```json
{
  "todo": {
    "id": 3,
    "title": "우유 사기",
    "completed": true,
    "createdAt": "2026-10-23T09:32:00.000Z"
  }
}
```

### 에러

| 상황 | 상태 코드 | code | message 예시 |
|------|------|------|------|
| id가 숫자가 아니거나 0 이하 | 400 | INVALID_ID | 올바르지 않은 할 일 번호입니다. |
| 본문이 JSON이 아님 | 400 | INVALID_JSON | 요청 형식이 올바르지 않습니다. |
| completed가 없거나 boolean이 아님 | 400 | VALIDATION_ERROR | 완료 여부는 true 또는 false여야 합니다. |
| 해당 id의 할 일이 없음 | 404 | NOT_FOUND | 할 일을 찾을 수 없습니다. |
| DB 오류 등 서버 문제 | 500 | INTERNAL_ERROR | 서버에 문제가 생겼습니다. 잠시 후 다시 시도해 주세요. |

에러 예시 (없는 할 일):

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "할 일을 찾을 수 없습니다."
  }
}
```

## 6. DELETE /api/todos/{id} (F-04 삭제)

할 일을 실제로 삭제한다. 삭제한 항목은 복구하지 않는다.

### 요청

- 경로 변수: `id` (양의 정수)
- 본문 없음

### 성공 응답: 204 No Content

응답 본문이 없다.

### 에러

| 상황 | 상태 코드 | code | message 예시 |
|------|------|------|------|
| id가 숫자가 아니거나 0 이하 | 400 | INVALID_ID | 올바르지 않은 할 일 번호입니다. |
| 해당 id의 할 일이 없음 (이미 삭제된 경우 포함) | 404 | NOT_FOUND | 할 일을 찾을 수 없습니다. |
| DB 오류 등 서버 문제 | 500 | INTERNAL_ERROR | 서버에 문제가 생겼습니다. 잠시 후 다시 시도해 주세요. |

## 7. 범위 밖

PRD에서 MVP 밖으로 정한 기능이라 API를 만들지 않는다.

- 제목 수정, 필터(v0.4)
- 로그인, 인증, 공유, 알림, 마감일, 카테고리
- 페이지 나누기(한 번에 전체 목록을 돌려준다)

## 8. 확인이 필요한 항목

- 제목 앞뒤 공백을 제거한 뒤 길이를 검사할지 (PRD, DATA_MODEL의 미결정 항목)
- 이미 삭제된 항목을 다시 삭제할 때 404 대신 204로 처리할지
- 화면 갱신 방식에 따라 PATCH/DELETE 응답에 목록 전체를 담을지 (TRD의 미결정 항목)
