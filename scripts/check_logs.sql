-- SQLite 깔끔한 테이블(Box) 뷰 포맷 설정
.mode table
.headers on

-- 1. 등록된 사용자 목록
SELECT 
    id, 
    username, 
    created_at 
FROM users;

-- 2. 최근 대화 로그 (최신 10건, 줄바꿈 제거 및 적정 길이 축약)
SELECT 
    c.id, 
    u.username, 
    CASE 
        WHEN length(c.user_message) > 15 THEN substr(c.user_message, 1, 13) || '..'
        ELSE c.user_message 
    END AS user_msg, 
    CASE 
        WHEN c.ai_response IS NULL THEN '-'
        WHEN length(c.ai_response) > 35 THEN substr(replace(replace(c.ai_response, char(10), ' '), char(13), ' '), 1, 33) || '..'
        ELSE replace(replace(c.ai_response, char(10), ' '), char(13), ' ')
    END AS ai_response, 
    COALESCE(c.error_status, 'OK') AS status, 
    c.created_at 
FROM chat_logs c
JOIN users u ON c.user_id = u.id
ORDER BY c.id DESC
LIMIT 10;

