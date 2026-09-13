## 1. 로깅 (Logging) 시스템 사용 이유

- 파이썬의 내장 `logging` 모듈은 서버 내부에서 일어나는 일들을 텍스트 형태로 터미널(콘솔)에 기록
- `main.py`에 다음과 같이 설정되어 있습니다.
- 과제 요구사항에 따라 user의 행동 추적 가능
```python
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("chatbot")
```

### 도입 목적 및 효과
1. **에러 추적 및 디버깅 (Troubleshooting)**: 해당 챗봇 프로젝트는 EC2와 같은 원격, 백그러운드 환경에서 동작함.
- 따라서 단순 print를 통해 에러를 출력할 경우 확인이 어려울 수 있음.
- `logger.error()`를 통해 에러의 원인을 터미널, 특정 파일에 출력하여 로그를 남길 수 있음
- 현재 로그는 filepath 미설정으로 터미널로 출력됨
- 단 AWS EC2 환경에서는 nohup을 통해 백그라운드로 서버를 실행함
    - 이 경우 리눅스 os가 터미널 출력을 받아서 **`nohup.out`**파일에 저장하여 로그 추적이 가능함.
2. **성능 모니터링 (Performance Monitoring)**: 
- logger를 통해 외부 API 통신 전후 시간을 측정하여 `latency_ms`를 로그로 남김
    - 이를 통해 서버 응답 지연시간을 모니터링 가능
3. **멀티 유저 요청 추적 (Traceability)**: 
- 서버에 동시 접속자가 많아 로그가 뒤섞일 가능성 있음.
- 모든 요청에 대해 고유 난수(`request_id`)와 `user_id`를 함께 기록
- 이를 통해 특정 유저의 질문이 어떤 흐름으로 처리되었는지 추적 가능

---

### 로그 세부 동작 파악
```bash
request_received user_id=2 path=/api/chat
INFO  ai_call_start user_id=2 request_id=23b26489
INFO  AFC is enabled with max remote calls: 10.
INFO  HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
INFO  ai_call_success request_id=23b26489 latency_ms=4070
INFO  db_save_success user_id=2 chat_id=7
INFO:     121.135.181.35:63305 - "POST /api/chat HTTP/1.1" 200 OK
INFO  request_received user_id=2 path=/api/chat
INFO  ai_call_start user_id=2 request_id=3082b40c
INFO  AFC is enabled with max remote calls: 10.
INFO  HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
INFO  ai_call_success request_id=3082b40c latency_ms=3656
INFO  db_save_success user_id=2 chat_id=8
INFO:     121.135.181.35:59617 - "POST /api/chat HTTP/1.1" 200 OK
INFO  request_received user_id=2 path=/api/chat
INFO  ai_call_start user_id=2 request_id=d88578c0
INFO  AFC is enabled with max remote calls: 10.
INFO  HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
INFO  ai_call_success request_id=d88578c0 latency_ms=897
INFO  db_save_success user_id=2 chat_id=9

```

### 로그 동작 분석
해당 로그는 `user_id=2`인 사용자가 총 3번의 채팅(질문)을 보냈고, 서버가 이를 모두 성공적으로 처리했음을 보여줍니다.

1. **사용자 요청 수신 및 식별 (Traceability)**
    * `request_received`: 유저 2번이 채팅을 전송함.
    * `ai_call_start`: 다른 유저의 요청과 섞이지 않도록 `23b26489`, `3082b40c` 등 고유 난수(request_id)를 발급하여 추적 시작.
2. **구글 Gemini API 통신 (Google SDK 로그)**
    * `AFC is enabled with max remote calls...` 및 `HTTP Request: POST...`
    * `google-genai` 라이브러리 내부에서 자체적으로 출력하는 로그로, 구글 서버로 API 요청을 보냈고 `200 OK`(정상 응답)를 받았음을 의미함.
3. **AI 응답 속도 성능 측정 (Latency)**
    * `latency_ms`: 첫 질문은 4070ms(약 4초), 두 번째는 3656ms, 세 번째는 897ms가 소요됨.
    * 설정한 타임아웃 이내에 안정적으로 응답이 도착했음을 확인.
4. **최종 DB 저장 완료**
    * `db_save_success`: AI가 준 답변을 기존 레코드에 업데이트하고 DB에 최종 `commit` 성공함 (chat_id 7, 8, 9).
5. **프론트엔드로 결과 반환**
    * `INFO: 121.135.181.35... "POST /api/chat HTTP/1.1" 200 OK`: FastAPI 프레임워크가 접속한 클라이언트에게 HTTP 200 상태 코드로 응답을 되돌려줌.

### 💡 (참고) 에러 및 서킷 브레이커 차단 로그
네트워크 지연이나 한도 초과(429) 시에는 아래와 같은 로그가 남아 장애 원인을 즉시 파악할 수 있습니다.
* `ai_call_failed request_id=... error=AI_TIMEOUT`: 설정한 시간을 초과하여 응답을 받지 못함.
* `circuit_breaker_active request_id=... blocked. Unlocks in 34s`: 구글 API 429 에러로 인해 잠금이 걸려 백엔드 내부에서 네트워크 통신을 차단(Fast-fail)했음을 의미.
