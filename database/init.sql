-- =========================================
-- Drop old tables if needed
-- Chỉ dùng khi bạn muốn reset database trong giai đoạn phát triển
-- =========================================

DROP TABLE IF EXISTS crawl_logs CASCADE;
DROP TABLE IF EXISTS analysis_results CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
DROP TABLE IF EXISTS authors CASCADE;
DROP TABLE IF EXISTS boards CASCADE;
DROP TABLE IF EXISTS platforms CASCADE;

-- =========================================
-- 1. Platforms
-- Ví dụ: PTT, Dcard, Facebook
-- =========================================

CREATE TABLE platforms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    base_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================
-- 2. Boards
-- Ví dụ: BeautySalon, MakeUp, Skincare
-- =========================================

CREATE TABLE boards (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(100),
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform_id, name)
);

-- =========================================
-- 3. Authors
-- 儲存文章作者
-- =========================================

CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================
-- 4. Articles
-- 儲存爬蟲抓下來的文章
-- =========================================

CREATE TABLE articles (
    id SERIAL PRIMARY KEY,

    unique_id VARCHAR(64) UNIQUE NOT NULL,

    platform_id INTEGER NOT NULL REFERENCES platforms(id),
    board_id INTEGER REFERENCES boards(id),
    author_id INTEGER REFERENCES authors(id),

    title TEXT NOT NULL,
    content TEXT,
    url TEXT,

    push_count INTEGER DEFAULT 0,

    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================
-- 5. Analysis Results
-- 儲存 LLM 分析結果與快取
-- 這張表故意不過度拆分，避免 AI 結果結構變動時很難維護
-- =========================================

CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,

    keyword VARCHAR(255) NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,

    result_json JSONB NOT NULL,

    expired_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(keyword, analysis_type)
);

-- =========================================
-- 6. Crawl Logs
-- 儲存每次爬蟲執行紀錄
-- =========================================

CREATE TABLE crawl_logs (
    id SERIAL PRIMARY KEY,

    platform_id INTEGER REFERENCES platforms(id),
    board_id INTEGER REFERENCES boards(id),

    status VARCHAR(50) NOT NULL,

    new_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,

    error_message TEXT,

    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

-- =========================================
-- Indexes
-- =========================================

CREATE INDEX idx_articles_platform_id
ON articles(platform_id);

CREATE INDEX idx_articles_board_id
ON articles(board_id);

CREATE INDEX idx_articles_author_id
ON articles(author_id);

CREATE INDEX idx_articles_published_at
ON articles(published_at);

CREATE INDEX idx_articles_push_count
ON articles(push_count);

CREATE INDEX idx_analysis_results_keyword_type
ON analysis_results(keyword, analysis_type);

CREATE INDEX idx_crawl_logs_started_at
ON crawl_logs(started_at);

CREATE INDEX idx_crawl_logs_status
ON crawl_logs(status);

-- Full text search indexes
CREATE INDEX idx_articles_title_fts
ON articles USING GIN (to_tsvector('simple', title));

CREATE INDEX idx_articles_content_fts
ON articles USING GIN (to_tsvector('simple', content));

-- =========================================
-- Initial seed data
-- =========================================

INSERT INTO platforms (name, display_name, base_url)
VALUES
    ('ptt', 'PTT', 'https://www.ptt.cc')
ON CONFLICT (name) DO NOTHING;

INSERT INTO boards (platform_id, name, display_name, url)
VALUES
    (
        (SELECT id FROM platforms WHERE name = 'ptt'),
        'BeautySalon',
        'BeautySalon',
        'https://www.ptt.cc/bbs/BeautySalon/index.html'
    ),
    (
        (SELECT id FROM platforms WHERE name = 'ptt'),
        'MakeUp',
        'MakeUp',
        'https://www.ptt.cc/bbs/MakeUp/index.html'
    ),
    (
        (SELECT id FROM platforms WHERE name = 'ptt'),
        'facelift',
        'facelift',
        'https://www.ptt.cc/bbs/facelift/index.html'
    )
ON CONFLICT (platform_id, name) DO NOTHING;

INSERT INTO boards (platform_id, name, display_name, url)
VALUES
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'Mix_Match', 'Mix_Match', 'https://www.ptt.cc/bbs/Mix_Match/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'fashion', 'fashion', 'https://www.ptt.cc/bbs/fashion/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'Brand', 'Brand', 'https://www.ptt.cc/bbs/Brand/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'e-shopping', 'e-shopping', 'https://www.ptt.cc/bbs/e-shopping/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'NailSalon', 'NailSalon', 'https://www.ptt.cc/bbs/NailSalon/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'Mancare', 'Mancare', 'https://www.ptt.cc/bbs/Mancare/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'teeth_salon', 'teeth_salon', 'https://www.ptt.cc/bbs/teeth_salon/index.html')
ON CONFLICT (platform_id, name) DO NOTHING;
