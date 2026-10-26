import { defineConfig } from "drizzle-kit";

// DB 종류는 MySQL, 접속 주소는 환경 변수에서 읽는다
export default defineConfig({
  dialect: "mysql",
  schema: "./src/lib/schema.ts",
  out: "./drizzle",
  dbCredentials: {
    url: process.env.DATABASE_URL ?? "",
  },
});
