CREATE TABLE community_fixed_message (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 500),
    updated_at INTEGER NOT NULL
);
INSERT INTO community_fixed_message (id, text, updated_at) VALUES (
    1,
    '시험 준비도 좋지만, 밥과 잠도 챙겨주세요. 오늘의 공부가 좋은 결과로 이어지길 크누아가 응원하겠습니다!',
    0
);
