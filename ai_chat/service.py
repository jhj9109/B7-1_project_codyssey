import asyncio
import logging
import os
import re
import time
from typing import List, Optional
from sqlalchemy.orm import Session
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from core import models
from core.config import settings
from ai_chat import repository

# 로거 초기화 (터미널 관련 로그 출력 제어)
logger = logging.getLogger("chatbot")

import json

def inspect_api_response(response):
    """
    API 응답 객체(또는 Dict)를 분석하여 주요 정보들을 보기 좋게 출력합니다.
    """
    # 1. 만약 SDK 응답 객체라면 딕셔너리로 변환 시도
    if not isinstance(response, dict):
        try:
            if hasattr(response, 'to_dict'):
                response_dict = response.to_dict()
            elif hasattr(response, 'dict'):
                response_dict = response.dict()
            else:
                # 객체의 __dict__ 속성 활용
                response_dict = vars(response)
        except Exception:
            print("⚠️ 응답을 딕셔너리로 변환할 수 없어 원본 객체로 진행합니다.")
            response_dict = response
    else:
        response_dict = response

    print("=" * 60)
    print("🔍 [AI API Response Inspector] 상세 분석 결과")
    print("=" * 60)

    # [1] Prompt Feedback 분석 (질문 자체에 대한 필터링 여부)
    prompt_feedback = response_dict.get("prompt_feedback") or response_dict.get("promptFeedback")
    if prompt_feedback:
        print("\n[1] 📝 Prompt Feedback (질문 분석)")
        block_reason = prompt_feedback.get("block_reason") or prompt_feedback.get("blockReason")
        if block_reason:
            print(f"  ❌ 질문이 차단되었습니다! 사유: {block_reason}")
        else:
            print("  ✅ 질문 사전 검사 통과 (차단 사유 없음)")
    else:
        print("\n[1] 📝 Prompt Feedback: 정보 없음 (정상 통과)")

    # [2] Candidates 분석 (답변 후보)
    candidates = response_dict.get("candidates", [])
    print(f"\n[2] 🤖 생성된 답변 후보 (Candidates): 총 {len(candidates)}개")

    for idx, candidate in enumerate(candidates):
        print(f"\n  👉 Candidate #{idx}")
        
        # Finish Reason (종료 원인)
        finish_reason = candidate.get("finish_reason") or candidate.get("finishReason")
        print(f"    - 생성 종료 사유 (Finish Reason): {finish_reason}")
        
        # Content 및 Text 출력
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        print(f"    - 답변 구성 요소 (Parts): {len(parts)}개")
        
        for p_idx, part in enumerate(parts):
            # 텍스트 형태인지 확인
            if isinstance(part, dict) and "text" in part:
                text_content = part["text"]
            elif hasattr(part, "text"):
                text_content = part.text
            else:
                text_content = str(part)
                
            # 너무 길면 앞부분만 요약 출력
            preview = text_content[:150].replace('\n', ' ') + "..." if len(text_content) > 150 else text_content
            print(f"      * Part [{p_idx}] 텍스트 예시: \"{preview}\"")

        # Safety Ratings (안전성 검사 결과)
        safety_ratings = candidate.get("safety_ratings") or candidate.get("safetyRatings", [])
        if safety_ratings:
            print("    - 🛡️ 안전성 등급 (Safety Ratings):")
            for rating in safety_ratings:
                # SDK 객체이거나 딕셔너리인 경우 모두 대응
                category = rating.get("category") if isinstance(rating, dict) else getattr(rating, "category", "")
                probability = rating.get("probability") if isinstance(rating, dict) else getattr(rating, "probability", "")
                
                # 유해 등급이 NEGLIGIBLE(무시할 만한 수준)이 아니면 경고 표시
                warn_flag = "⚠️" if probability not in ["NEGLIGIBLE", "LOW", "HARM_PROBABILITY_NEGLIGIBLE"] else "✅"
                print(f"      {warn_flag} {category:<30} : {probability}")

    # [3] 토큰 사용량 정보 (Usage Metadata)
    usage = response_dict.get("usage_metadata") or response_dict.get("usageMetadata")
    if usage:
        print("\n[3] 📊 사용된 토큰 정보 (Usage Metadata)")
        prompt_tokens = usage.get("prompt_token_count") or usage.get("promptTokenCount", 0)
        candidate_tokens = usage.get("candidates_token_count") or usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("total_token_count") or usage.get("totalTokenCount", 0)
        
        print(f"  - 입력 토큰 (Prompt): {prompt_tokens} tokens")
        print(f"  - 출력 토큰 (Candidates): {candidate_tokens} tokens")
        print(f"  - 전체 토큰 (Total): {total_tokens} tokens")

    print("\n" + "=" * 60)

class AITimeoutError(Exception):
    """AI API 호출 타임아웃 시 발생하는 예외"""
    pass

# gemini api를 호출하여 ai 응답을 생성, 반환하는 함수
# 이전 대화 기록 (context)를 넣어 문맥을 유지함. (최대 과거 채팅 이력 3개까지)
# 사용자의 최신 질문 (prompt)을 함께 제공 
# 시간 내 미응답 시 타임아웃 발생시킴 
def build_ai_contents(prompt: str, context: Optional[List[models.ChatLog]] = None) -> List[types.Content]:
    """사용자 프롬프트와 과거 대화 기록을 Google GenAI SDK가 요구하는 포맷으로 변환합니다."""
    contents = []
    if context:
        for log in context:
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=log.user_message)]))
            if log.ai_response:
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=log.ai_response)]))
    
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
    return contents

async def generate_response(prompt: str, context: List[models.ChatLog] = None) -> str:
    
    # API 키가 환경 변수에 설정되어 있지 않은 경우 더미 응답 반환
    if not settings.gemini_api_key:
        logger.warning("Gemini API Key is not set. Returning dummy response.")
        return "I am a dummy AI. Please configure GEMINI_API_KEY in your .env file to enable real AI responses."

    # gemini api key를 기반으로 gemini client 초기화
    client = genai.Client(api_key=settings.gemini_api_key)
    
    contents = build_ai_contents(prompt, context)

    try:
        # client.aio를 사용하여 네이티브 비동기로 API 호출
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=contents
            ),
            timeout=settings.ai_timeout_seconds
        )

        inspect_api_response(response)
        
        # 모델의 응답이 안전성(Safety) 필터에 의해 차단되었거나 비어있는 경우 처리
        if not response.text:
            raise genai_errors.APIError(message="AI response was blocked or empty.")
            
        return response.text

    except asyncio.TimeoutError:
        # 제한 시간이 초과된 경우
        logger.error("AI API call timed out")
        raise AITimeoutError("AI_TIMEOUT")
    except genai_errors.ClientError as e:
        # 4xx 에러: 잘못된 요청, 인증 실패, 쿼터 초과 등
        logger.error(f"AI ClientError: {e.message}")
        raise
    except genai_errors.ServerError as e:
        # 5xx 에러: 구글 서버 내부 오류
        logger.error(f"AI ServerError: {e.message}")
        raise
    except genai_errors.APIError as e:
        # 기타 API 오류
        logger.error(f"AI APIError: {e.message}")
        raise
    except Exception as e:
        # 그 외 예상치 못한 에러
        logger.exception("Unexpected error calling AI API")
        raise e


def extract_retry_seconds(error: Exception) -> Optional[int]:
    """
    API 429 에러 메시지(예: 'Please retry in 24.59911155s.')에서 
    재시도까지 남은 대기 시간(초)을 추출하여 반올림한 정수로 반환합니다.
    추출 실패 시 None을 반환합니다.
    """
    error_str = str(error)
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_str, re.IGNORECASE)
    if match:
        try:
            return max(1, round(float(match.group(1))))
        except (ValueError, TypeError):
            return None
    return None


# Rate Limit 서킷 브레이커를 위한 글로벌 잠금 해제 시간
# 이 시간(timestamp) 전까지는 구글 API 호출을 원천 차단하고 Fast-fail 처리합니다.
GLOBAL_RATE_LIMIT_UNLOCK_TIME = 0.0

# 사용자에게 전달할 에러 안내 메시지 매핑 테이블
AI_ERROR_MESSAGES = {
    "AI_TIMEOUT": "현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요.",
    "AI_RATE_LIMIT": "현재 이용량이 많아 요청 한도를 초과했습니다. 약 1분 뒤에 다시 시도해 주세요.",
    "AI_AUTH_ERROR": "AI 서비스 인증 오류가 발생했습니다. 관리자에게 문의해 주세요.",
    "AI_INVALID_REQUEST": "질문 요청 형식이 올바르지 않습니다. 다시 입력해 주세요.",
    "AI_CLIENT_ERROR": "요청 처리 중 오류가 발생했습니다. 질문을 다시 확인해 주세요.",
    "AI_SERVER_ERROR": "AI 서버(Google)에 일시적인 장애가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    "AI_API_ERROR": "AI 서비스 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    "AI_ERROR": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
}


async def execute_ai_call_with_handling(message: str, context_logs: List[models.ChatLog], request_id: str) -> tuple[Optional[str], Optional[str]]:
    """
    AI를 호출하고 서킷 브레이커 및 예외 처리를 수행합니다.
    반환값: (ai_response_text, error_status)
    """
    global GLOBAL_RATE_LIMIT_UNLOCK_TIME
    
    # [서킷 브레이커] 현재 시간이 잠금 해제 시간보다 이전이면 
    # 구글 API 호출을 생략하고 즉시 한도 초과 에러 반환 (Fast-fail)
    if time.time() < GLOBAL_RATE_LIMIT_UNLOCK_TIME:
        remaining_sec = int(GLOBAL_RATE_LIMIT_UNLOCK_TIME - time.time())
        logger.warning(f"circuit_breaker_active request_id={request_id} blocked. Unlocks in {remaining_sec}s")
        return AI_ERROR_MESSAGES["AI_RATE_LIMIT"], "AI_ERROR"

    start_time = time.time()
    try:
        ai_response_text = await generate_response(message, context_logs)
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"ai_call_success request_id={request_id} latency_ms={latency_ms}")
        return ai_response_text, None
    except AITimeoutError:
        error_status = "AI_TIMEOUT"
        logger.error(f"ai_call_failed request_id={request_id} error={error_status}")
        return AI_ERROR_MESSAGES["AI_TIMEOUT"], error_status
    except genai_errors.ClientError as e:
        error_status = "AI_ERROR"
        if getattr(e, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(e).upper():
            lock_duration = (extract_retry_seconds(e) or 60) + 5
            GLOBAL_RATE_LIMIT_UNLOCK_TIME = time.time() + lock_duration
            logger.error(f"ai_call_failed request_id={request_id} error={error_status} msg=RateLimit, circuit_breaker locked for {int(lock_duration)}s")
            return AI_ERROR_MESSAGES["AI_RATE_LIMIT"], error_status
        elif getattr(e, "code", None) in (401, 403):
            logger.error(f"ai_call_failed request_id={request_id} error={error_status} msg=AuthError")
            return AI_ERROR_MESSAGES["AI_AUTH_ERROR"], error_status
        elif getattr(e, "code", None) == 400:
            logger.error(f"ai_call_failed request_id={request_id} error={error_status} msg=InvalidRequest")
            return AI_ERROR_MESSAGES["AI_INVALID_REQUEST"], error_status
        else:
            logger.error(f"ai_call_failed request_id={request_id} error={error_status} code={getattr(e, 'code', None)} details={getattr(e, 'message', str(e))}")
            return AI_ERROR_MESSAGES["AI_CLIENT_ERROR"], error_status
    except genai_errors.ServerError as e:
        error_status = "AI_ERROR"
        logger.error(f"ai_call_failed request_id={request_id} error={error_status} details={getattr(e, 'message', str(e))}")
        return AI_ERROR_MESSAGES["AI_SERVER_ERROR"], error_status
    except genai_errors.APIError as e:
        error_status = "AI_ERROR"
        logger.error(f"ai_call_failed request_id={request_id} error={error_status} details={getattr(e, 'message', str(e))}")
        return AI_ERROR_MESSAGES["AI_API_ERROR"], error_status
    except Exception as e:
        error_status = "AI_ERROR"
        logger.exception(f"ai_call_failed request_id={request_id} error={error_status}")
        return AI_ERROR_MESSAGES["AI_ERROR"], error_status

async def process_chat(db: Session, user_id: int, message: str) -> models.ChatLog:
    """
    채팅 처리 메인 비즈니스 파이프라인:
    1. 고유 request_id 생성 및 로깅
    2. 최근 3개 대화 기록 조회 및 순서 정렬
    3. 사용자 질문 1차 DB 선저장
    4. AI 응답 생성 및 예외 처리
    5. AI 응답 및 에러 상태 2차 DB 업데이트
    """
    # 요청 추적용 고유 난수 생성 (4 바이트 -> 8자리 16진수)
    request_id = os.urandom(4).hex()
    logger.info(f"request_received user_id={user_id} path=/api/chat")

    # DB에서 사용자의 최근 채팅 기록 3개 조회 (내림차순, 즉 최신순)
    context_logs = repository.get_recent_chats_by_user_id(db, user_id=user_id, limit=3)
    # AI가 시간순으로 읽을 수 있도록 뒤집음
    context_logs.reverse()

    # 1차 저장: AI 호출 전 사용자의 질문을 DB에 먼저 영구 저장
    new_chat = repository.create_chat_log(db, user_id=user_id, user_message=message)

    logger.info(f"ai_call_start user_id={user_id} request_id={request_id}")

    # 2. AI 호출 및 예외 처리 위임
    ai_response_text, error_status = await execute_ai_call_with_handling(message, context_logs, request_id)

    # 2차 업데이트: AI 응답 또는 에러 상태를 DB에 업데이트
    updated_chat = repository.update_chat_response(
        db=db,
        chat_log=new_chat,
        ai_response=ai_response_text,
        error_status=error_status
    )

    if error_status:
        logger.info(f"db_save_failure user_id={user_id} chat_id={updated_chat.id} error={error_status}")
    else:
        logger.info(f"db_save_success user_id={user_id} chat_id={updated_chat.id}")

    return updated_chat


def get_chat_history(db: Session, user_id: int) -> List[models.ChatLog]:
    """사용자의 전체 과거 대화 기록을 시간순(오름차순)으로 조회합니다."""
    return repository.get_all_chats_by_user_id(db, user_id=user_id)
