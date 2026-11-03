# TeamBrain 소개 웹페이지 (랜딩 페이지)

비개발자에게 TeamBrain을 소개하는 **광고용 웹페이지**입니다. React + TypeScript(Next.js)로 만들었습니다. (검색엔진 노출(SEO)을 위해 Next.js 사용)

## 처음 한 번만: 준비하기

이 폴더(`landing`)에서 아래를 한 번 실행합니다. (Node.js가 설치되어 있어야 합니다)

```bash
npm install
```

## 화면으로 직접 보기 (개발 모드)

```bash
npm run dev
```

실행하면 터미널에 `http://localhost:3000` 같은 주소가 나옵니다. 그 주소를 브라우저에서 열면 페이지가 보입니다. (파일을 고치면 화면이 자동으로 새로고침됩니다.)

## 글자만 바꾸고 싶을 때

디자인·코드를 몰라도 됩니다. **`src/data/content.ts`** 파일을 열어서 큰따옴표(`" "`) 안의 글자만 고치면 페이지 내용이 바뀝니다.

검색결과에 뜨는 제목·설명 문구는 **`src/app/layout.tsx`**의 `metadata` 부분에 있습니다.

## 실제 배포용으로 만들기 (선택)

```bash
npm run build
```

배포는 Vercel(Next.js 만든 회사의 무료 호스팅 서비스)을 쓰는 걸 권장합니다 — 이 레포를 Vercel에 GitHub로 연결해두면 `git push`만으로 자동 배포됩니다. 별도 서버 설정(S3·CloudFront 같은)이 필요 없습니다.

---

Port_051 · 2026 SW마에스트로 제17기
