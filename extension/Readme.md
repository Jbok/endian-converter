# Excel 표 형식으로 복사 (VSCode Extension)

VSCode에서 선택한 텍스트를 **엑셀 표 형식(HTML table)** 으로 클립보드에 올려줍니다.  
Slack, Teams 등 사내 메신저에 붙여넣으면 일반 텍스트가 아닌 **표**로 인식됩니다.

---

## 작동 원리

```
[VSCode 선택] → 줄 = 행, 탭 = 열로 파싱
             → text/plain + text/html(<table>) 동시에 클립보드에 등록
             → 메신저가 text/html 감지 → 표로 렌더링
```

일반 복사(`Ctrl+C`)는 `text/plain`만 올리지만,  
이 익스텐션은 `text/html`을 **함께** 올리기 때문에 메신저가 표로 인식합니다.

---

## 사용법

### 설치

```bash
# .vsix 파일로 설치 (vsce로 패키징 후)
code --install-extension excel-copy-0.1.0.vsix

# 또는 VSCode에서: Extensions → ... → Install from VSIX
```

### 개발 모드로 바로 실행

1. 이 폴더를 VSCode로 열기
2. `F5` 키 → Extension Development Host 실행
3. 새 창에서 텍스트 선택 후 테스트

### 사용

1. VSCode에서 텍스트 선택
2. `Ctrl+Shift+E` (Mac: `Cmd+Shift+E`) 또는 우클릭 → **"Excel 표 형식으로 복사"**
3. 메신저 입력창에 `Ctrl+V`로 붙여넣기

---

## 입력 → 출력 예시

**선택한 텍스트 (탭 구분):**
```
이름	나이	팀
홍길동	30	백엔드
김철수	25	프론트
```

**클립보드에 올라가는 HTML:**
```html
<table>
  <tr><td>이름</td><td>나이</td><td>팀</td></tr>
  <tr><td>홍길동</td><td>30</td><td>백엔드</td></tr>
  <tr><td>김철수</td><td>25</td><td>프론트</td></tr>
</table>
```

**탭이 없는 경우** → 줄마다 1열짜리 행으로 처리됩니다.

---

## OS별 동작 방식

| OS | 사용 방법 |
|---|---|
| macOS | `osascript` (JXA)로 NSPasteboard에 직접 등록 — 별도 설치 불필요 |
| Windows | PowerShell로 CF_HTML 포맷 생성 후 Clipboard에 등록 |
| Linux | `xclip` 사용 (`sudo apt install xclip` 필요) |

---

## .vsix 패키징 방법

```bash
npm install -g @vscode/vsce
cd excel-copy-extension
vsce package
# → excel-copy-0.1.0.vsix 생성됨
```
