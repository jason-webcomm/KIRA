# Gitea 통합

Gitea API와 통합하면 KIRA가 코드 저장소를 관리할 수 있습니다.

## 📋 사전 요구사항

- Gitea 계정 (gitea.com 또는 자체 호스팅)
- 개인 액세스 토큰
- HTTP 모드로 실행 중인 Gitea MCP 서버

---

## 🔑 1단계: 액세스 토큰 생성

### 1. Gitea 접속
- [Gitea.com](https://gitea.com) 또는 회사 Gitea 서버

### 2. 개인 액세스 토큰 생성
1. 우측 상단 프로필 아이콘 클릭
2. **"설정"** 선택
3. 좌측 메뉴에서 **"애플리케이션"** 클릭
4. **"액세스 토큰"** 섹션으로 스크롤
5. **"새 토큰 생성"** 클릭

### 3. 토큰 구성
- **토큰 이름**: `KIRA Bot` (원하는 이름)
- **만료일**: 만료 설정 (선택 사항)
- **범위 선택**: 다음 권한 선택
  - ✅ `read:repository` - 저장소 읽기
  - ✅ `write:repository` - 저장소 쓰기
  - ✅ `read:user` - 사용자 정보 읽기
  - ✅ `read:issue` - 이슈 읽기
  - ✅ `write:issue` - 이슈 쓰기

### 4. 토큰 생성 및 복사
1. **"토큰 생성"** 클릭
2. 생성된 토큰 복사 (한 번만 표시됩니다!)
3. 안전하게 보관

::: warning 토큰 보안
개인 액세스 토큰은 한 번만 표시됩니다.
안전하게 보관하며 다시 볼 수 없습니다.
:::

---

## 🌐 2단계: Gitea MCP 서버 시작 (HTTP 모드)

Gitea MCP 서버가 HTTP 모드로 실행 중이어야 KIRA가 연결할 수 있습니다.

### 옵션 A: 로컬에서 실행

1. Gitea MCP 서버 설치:
```bash
npm install -g gitea-mcp
```

2. HTTP 모드로 서버 시작:
```bash
gitea-mcp --transport streamable-http --port 8080
```

서버는 `http://localhost:8080/mcp`에서 사용 가능합니다.

### 옵션 B: Docker로 실행

```bash
docker run -d \
  -p 8080:8080 \
  -e GITEA_ACCESS_TOKEN=<your_token> \
  gitea/gitea-mcp:latest \
  --transport streamable-http --port 8080
```

---

## ⚙️ 3단계: KIRA 구성

### 1. KIRA 앱 실행
환경 변수 탭을 엽니다.

### 2. Gitea 섹션 찾기
**MCP 설정** > **Gitea**

### 3. 설정 활성화
- 토글 스위치를 **ON**으로 설정

### 4. 정보 입력
- **GITEA_HOST**: Gitea 서버 URL
  - Gitea.com: `https://gitea.com`
  - 자체 호스팅: `https://git.company.com`
- **GITEA_ACCESS_TOKEN**: 복사한 액세스 토큰
- **GITEA_MCP_HTTP_URL**: MCP 서버 HTTP URL
  - 로컬: `http://localhost:8080/mcp`
  - 원격: `http://your-server:8080/mcp`

### 5. 설정 저장
- **"설정 저장"** 버튼 클릭
- 서버 재시작

---

## ✅ 4단계: 테스트

Slack에서 KIRA에게 물어보세요:

```
내 Gitea 저장소 보여줘
```

```
"myapp" 저장소의 최근 커밋 알려줘
```

KIRA가 Gitea API를 통해 정보를 가져옵니다.

---

## 🎯 사용 예시

### 저장소 조회
```
사용자: Gitea 저장소 목록 보여줘
KIRA: [Gitea 쿼리]
      1. user/project-alpha
      2. user/project-beta
      3. my-app
```

### 이슈 관리
```
사용자: "my-app" 저장소에 이슈 생성: "버그 수정 필요"
KIRA: [Gitea 이슈 생성됨] #42 이슈 생성됨.
```

### 커밋 조회
```
사용자: "my-app"의 최근 5개 커밋 보여줘
KIRA: [Gitea 쿼리]
      1. fix: 로그인 버그 수정
      2. feat: 새로운 기능 추가
      ...
```

### Pull Request 조회
```
사용자: 내 PR들 보여줘
KIRA: [Gitea 쿼리]
      1. PR #123: 기능 개선
      2. PR #124: 버그 수정
```

---

## 🔧 문제 해결

### "MCP 서버 시작 실패"
- Gitea MCP 서버가 실행 중인지 확인
- `GITEA_MCP_HTTP_URL`이 올바른지 확인
- KIRA에서 서버에 접근할 수 있는지 확인

### "인증 실패"
- 액세스 토큰이 올바른지 확인
- 토큰 만료 여부 확인
- Gitea에서 토큰이 활성 상태인지 확인

### "연결 거부됨"
- 지정된 포트에서 Gitea MCP 서버가 실행 중인지 확인
- 방화벽 설정 확인
- URL 프로토콜(http/https)이 올바른지 확인

### "권한 거부됨"
- 액세스 토큰 권한(범위) 확인
- `read:repository`, `write:repository` 권한 필요
- 저장소 접근 권한 확인

### 특정 저장소에 접근 불가
- 해당 저장소의 멤버인지 확인
- 저장소가 비공개인 경우 권한 확인

---

## 💡 팁

### 자체 호스팅 Gitea
내부 회사 Gitea 서버 사용 시:
- GITEA_HOST에 회사 Gitea 주소 입력
- 예: `https://git.company.com`

### MCP 서버 배포
프로덕션 배포 시:
- 전용 머신에서 MCP 서버 실행
- 적절한 SSL 인증서로 HTTPS 사용
- 필요한 경우 역방 프록시(nginx) 구성
- 서버 실행 유지를 위한 프로세스 매니저(systemd, PM2) 설정

### 토큰 관리
- 명확한 토큰 이름 설정 (`KIRA Bot`)
- 보안을 위해 만료일 설정
- 주기적으로 토큰 교체

### 최소 권한 부여
필요한 권한만 부여:
- 읽기 전용: `read:repository`만 선택
- 쓰기 필요: `write:repository` 추가
- 전체 액세스: `read:user`, `read:issue`, `write:issue` 추가

### 효과적 사용
- `owner/repo` 형식으로 저장소 이름 명확히 지정
- 브랜치 이름 정확히 입력
- 이슈/PR 번호로 빠른 조회

---

## 🔗 관련 링크

- [Gitea 문서](https://docs.gitea.com/)
- [Gitea MCP Server](https://gitea.com/gitea/gitea-mcp)
- [개인 액세스 토큰](https://docs.gitea.com/next/usage/advanced/applications)