# 핵심 로직 상세 동작 분석

## 1. Gemini API 통신 로직 (`ai_chat/service.py - generate_response`)

- 구글의 gemini SDK인 `google-genai` 패키지를 사용하여 외부 AI 서버와 통신, 답변을 반환하는 함수
- 매개변수로 사용자의 질문(str)과 과거 대화 내역 최대 3건(list)를 받는다.
- `router.py`의 chat 함수가 이를 사용한다.

### 세부 동작 단계
1. **클라이언트 초기화**: 환경 변수(`.env`)의 `GEMINI_API_KEY`를 주입하여 구글 서버와 통신할 수 있는 인증된 `client` 객체 생성
2. **문맥(Context) 데이터 규격화**: Gemini AI 자체는 기억력이 없으므로 과거 대화 내역을 함께 전송해야 함
    *   DB에서 불러온 기록을 순회하며, 유저의 말은 `role="user"`로, AI의 대답은 `role="model"`로 분류
    *   이를 구글 SDK 데이터 구조인 `types.Content`와 `types.Part.from_text()` 형태로 변환하여 `contents` 배열에 쌓음
3. **새로운 프롬프트 추가**: 과거 내역 포장이 끝나면, 사용자가 방금 입력한 새로운 질문을 배열 맨 끝에 `role="user"`로 추가
4. **비동기 API 전송 및 응답 추출**:
    *   완성된 `contents`를 `gemini-2.5-flash` 모델에게 전송
    *   이때 네트워크 지연(2~3초) 동안 FastAPI 서버가 멈추지 않도록 **`asyncio.to_thread`**를 사용해 백그라운드 스레드로 처리
    *   구글이 반환한 응답 객체 중 순수 문장 데이터인 `.text` 속성만 뽑아 반환

---

## 2. 메인 채팅 파이프라인 (`Router ➡️ Service ➡️ Repository`)

- 사용자가 화면에서 전송 버튼을 눌렀을 때 `router.py`(`chat`)가 요청을 받아 `service.py`(`process_chat`) 및 `repository.py`로 이어지는 파이프라인을 실행합니다.
- **인증(Router) ➡️ 조회(Repository) ➡️ 1차 저장(Repository) ➡️ AI 호출(Service) ➡️ 2차 저장(Repository)**의 계층형 파이프라인으로 구성.

### 세부 동작 단계
1. **인증 및 요청 수신 (Router)**: `Depends(get_current_user)`가 작동하여 JWT 토큰이 유효한지 검사하고 유저 정보를 획득한 뒤 Service 계층에 위임합니다.
2. **요청 추적 및 과거 대화 기억 조회 (Service ➡️ Repository)**:
    - 요청 추적용 고유 난수(`request_id`)를 발급합니다.
    - `repository.get_recent_chats_by_user_id`를 호출하여 DB에서 해당 유저의 최근 채팅 기록 3개를 내림차순(최신순)으로 가져옵니다. 
    - AI가 순서대로 읽을 수 있게 `reverse()`로 뒤집습니다.
3. **유저 질문 1차 DB 저장 (Service ➡️ Repository)**:
    - AI를 호출하기 **전**에 `repository.create_chat_log`를 통해 사용자가 친 채팅을 먼저 DB에 영구 저장(`commit`)합니다. 
    - 만약 이후 AI 통신 과정에서 구글 서버가 오류를 내더라도 사용자의 질문 데이터는 손실되지 않습니다.
4. **AI 호출 및 예외(에러) 처리 (Service)**:
    - `generate_response()`를 호출하여 답변을 대기합니다. 
    - 만약 타임아웃이나 서버 에러 등 예외(`Exception`)가 발생하면 시스템이 죽지 않고 `except` 블록으로 빠져나와, 
    - 화면에 뿌려줄 **사용자 친화적 한국어 안내 메시지**와 에러 상태 코드(`error_status`)를 대신 생성합니다.
5. **AI 답변 최종 DB 업데이트 (Service ➡️ Repository)**:
    - 3단계에서 만들어둔 레코드에 AI 응답(또는 에러 안내문)을 채워 넣고 `repository.update_chat_response`를 통해 최종 `commit` 한 뒤 프론트엔드로 응답을 넘겨줍니다.

