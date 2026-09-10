# 핵심 로직 상세 동작 분석

## 1. 프롬프트 조합 및 비동기 API 통신 (`ai_chat/service.py`)

- `build_ai_contents`: 사용자 질문과 과거 문맥을 조립하여 구글 SDK 규격(`types.Content`)으로 변환합니다.
- `execute_ai_call_with_handling`: 서킷 브레이커 검사와 실제 비동기 통신을 담당하고 에러를 핸들링합니다.

### 세부 동작 단계
1. **문맥(Context) 데이터 규격화 (`build_ai_contents`)**: 
    *   DB에서 불러온 기록을 순회하며, 유저의 말은 `role="user"`로, AI의 대답은 `role="model"`로 분류하여 `contents` 배열에 쌓음
    *   마지막에 사용자가 방금 입력한 새로운 질문을 배열 맨 끝에 `role="user"`로 추가
2. **서킷 브레이커 검사 (차단기)**:
    *   `execute_ai_call_with_handling` 내에서 `GLOBAL_RATE_LIMIT_UNLOCK_TIME`과 현재 시간을 비교
    *   만약 잠금 상태라면 구글 API를 호출하지 않고 백엔드에서 0.001초 만에 즉시(Fast-fail) 429 한도 초과 에러 반환
3. **네이티브 비동기 API 전송 (`client.aio`)**:
    *   완성된 `contents`를 `settings.gemini_model` 모델에게 전송
    *   구글의 `client.aio.models.generate_content`를 활용해 파이썬의 `await` 방식으로 네이티브 비동기 네트워크 통신 수행 (서버 차단 방지)
    *   결과값 중 순수 문장 데이터인 `.text` 속성만 뽑아 반환하며, 에러(429, 500 등) 발생 시 사용자 친화적인 메시지와 에러 코드로 변환하여 반환

---

## 2. 메인 채팅 파이프라인 (`Router ➡️ Service ➡️ Repository`)

- `router.py`(`chat`)가 요청을 받아 `service.py`(`process_chat`) 및 `repository.py`로 이어지는 3계층 파이프라인.
- **인증(Router) ➡️ 조회(Repository) ➡️ 1차 저장(Repository) ➡️ AI 호출(Service) ➡️ 2차 저장(Repository)**의 구조.

### 세부 동작 단계
1. **인증 및 요청 수신 (Router)**: `Depends(get_current_user)`가 작동하여 토큰을 검사하고 유저 정보를 획득한 뒤 Service에 위임합니다.
2. **요청 추적 및 과거 대화 기억 조회 (Repository)**:
    - `get_recent_chats_by_user_id`를 호출하여 해당 유저의 최근 기록 3개를 불러옵니다.
    - 💡 **핵심**: 이때 `error_status`가 `None`인 정상 대화만 가져오도록 필터링하여, 실패한 과거 대답이 AI의 문맥을 오염시키는 것을 100% 방지합니다.
3. **유저 질문 1차 DB 저장 (Repository)**:
    - AI 통신 전 `create_chat_log`로 유저 질문을 선저장(Commit)하여, 서버 에러 시에도 질문 데이터 손실을 막습니다.
4. **AI 호출 및 예외(에러) 처리 (Service)**:
    - `execute_ai_call_with_handling()`을 호출하여 구글 서버와 통신합니다. 
    - 에러나 타임아웃 발생 시 뻗지 않고 사용자 친화적 문구와 규격화된 상태코드(`AI_TIMEOUT`, `AI_ERROR`)를 반환합니다.
5. **AI 답변 최종 DB 업데이트 (Repository)**:
    - 1차 저장한 레코드에 AI 응답(또는 에러 안내문)과 상태 코드를 채워 넣고 최종 `commit` 한 뒤 프론트엔드로 리턴합니다.

