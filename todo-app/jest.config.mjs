import nextJest from "next/jest.js";

// Next.js 설정(tsconfig, 환경 변수 등)을 Jest에 연결
const createJestConfig = nextJest({ dir: "./" });

const config = {
  testEnvironment: "jest-environment-jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    // tsconfig의 "@/*" 경로 별칭과 맞춘다
    "^@/(.*)$": "<rootDir>/$1",
  },
};

export default createJestConfig(config);
