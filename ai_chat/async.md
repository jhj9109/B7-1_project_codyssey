# 비동기 처리 (async, await, asyncio.to_thread)에 관하여

- 기본적으로 `def` 키워드 함수는 동기 방식으로 동작한다.
    - 즉 함수 안의 코드를 위에서 부터 순서대로 차례대로 실행한다.
- 단 def 키워드 앞에 `async` 키워드를 선언할 경우 해당 함수는 비동기 처리됨.
    - 타 함수의 완료를 기다리지 않고 동시에 여러 작업을 수행하는 방식

- 비동기 함수는 기본적으로 async로 선언된 비동기 함수 내에서 `await` 키워드를 붙여서 호출
    - `await`을 만난 비동기 함수는 실행을 잠시 멈추고, 해당 함수가 리턴될 때까지 다른 비동기 함수에게 실행 권한을 넘김

---

# `generate_response` 함수의 비동기 처리 구조 분석

`ai_chat/service.py`에 정의된 `generate_response` 함수는 외부 API(Gemini API) 호출로 인해 발생할 수 있는 I/O 병목 현상을 방지하기 위해 파이썬의 `asyncio` 모듈을 적극적으로 활용하고 있습니다. 비동기 처리 관점에서 이 함수의 핵심 동작(`async`, `await`, `asyncio.to_thread`)을 정리하면 다음과 같습니다.

## 1. `async def`와 `await`를 통한 비동기 흐름 제어
- **`async def` (코루틴 선언):** `generate_response` 및 내부의 `_call_api` 함수는 모두 `async def`로 선언된 코루틴(Coroutine)입니다.
- **`await` (제어권 양보):** 코루틴 내부에서 I/O 대기가 필요한 지점에 `await` 키워드를 사용합니다. 네트워크 요청이나 대기 시간이 발생할 때, 해당 작업이 완료될 때까지 대기하면서 메인 이벤트 루프(Event Loop)의 제어권을 반환합니다. 
- 이를 통해 해당 API 호출이 완료되기를 기다리는 동안 프로세스가 멈춰(Blocking) 있는 것이 아니라, FastAPI와 같은 비동기 프레임워크가 다른 사용자의 요청을 동시에 처리할 수 있도록 동시성(Concurrency)을 확보합니다.

## 2. `client.aio`를 활용한 네이티브 비동기 통신 (Non-blocking I/O)
```python
response = await asyncio.wait_for(
    client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=contents
    ),
    timeout=settings.ai_timeout_seconds
)
```
- **문제점:** 만약 동기(Synchronous) 방식으로 동작하는 I/O 바운드 함수를 비동기 코루틴 안에서 직접 호출하게 되면, API 응답이 올 때까지 FastAPI의 이벤트 루프 전체가 차단(Block)되는 치명적인 성능 저하가 발생합니다.
- **해결책 (`client.aio`):** 구글 라이브러리에서 공식 지원하는 비동기 클라이언트인 `client.aio`를 활용하여 네트워크 통신을 진행합니다.
- **`await` 결합:** 네트워크 통신이 처리되는 동안 메인 스레드의 이벤트 루프는 멈추지 않고 다른 태스크(다른 사용자의 채팅 등)를 유연하게 실행할 수 있습니다. 

## 3. `asyncio.wait_for`를 활용한 비동기 타임아웃 관리
- 메인 비동기 흐름에서는 무한정 응답을 기다리는 대신, `asyncio.wait_for`로 감싸서 제한 시간(`timeout`)을 설정합니다.
- 외부 API 서버에 장애가 생겨 응답이 지정된 시간 내에 오지 않으면, 대기 중인 코루틴을 강제 취소하고 즉시 `TimeoutError` 예외를 발생시켜 시스템을 방어합니다.
