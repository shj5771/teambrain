import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// base: "./" — 빌드 결과를 어느 경로에서 열어도 자원 경로가 깨지지 않도록 상대 경로 사용
export default defineConfig({
    plugins: [react()],
    base: "./",
});
