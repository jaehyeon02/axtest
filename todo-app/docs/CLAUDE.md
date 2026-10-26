# CLAUDE.md - Todo App

## 프로젝트 개요

혼자 쓰는 간단한 할 일 목록 웹 앱 (초보자 학습용)

## 기술 스택

- Next.js 15 (App Router), React 19, TypeScript (strict)
- Tailwind CSS
- DB: MySQL + Drizzle ORM
- 검증: Zod
- 테스트: Jest + React Testing Library

## 폴더 구조

- `app/`: 페이지와 API 라우트
- `src/components/`: 화면 컴포넌트
- `src/lib/`: 서버 로직, DB
- `src/types/`: 공유 타입
- `docs/`: 명세 문서

## 반드시 참고할 문서

- `docs/PRD.md`, `docs/TRD.md`, `docs/DATA_MODEL.md`
- `docs/API_SPEC.md`, `docs/COMPONENT_SPEC.md`, `docs/TEST_CASES.md`

## 규칙

- 명세에 없는 기능을 임의로 추가하지 말 것
- `any` 타입 금지
- 한 번에 한 기능만 작업하고, 끝나면 무엇을 바꿨는지 요약할 것
- 테스트를 삭제하거나 스킵하지 말 것
- 테스트가 실패하면 테스트가 아닌 구현을 고칠 것
- `console.log`는 디버깅 후 제거할 것
- 초보자가 이해할 수 있게 주석은 한국어로 짧게

## 자주 쓰는 명령

- 개발 서버: `npm run dev`
- 테스트: `npm test`