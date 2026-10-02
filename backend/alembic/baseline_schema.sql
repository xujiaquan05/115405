-- Frozen pre-Alembic schema. Do not regenerate from future application models.
-- Later revisions own analysis_history, locks, vectors and last_crawled_at.

CREATE TABLE IF NOT EXISTS alerts (
	id SERIAL NOT NULL,
	user_id INTEGER,
	keyword VARCHAR(255) NOT NULL,
	level VARCHAR(20) NOT NULL,
	title VARCHAR(255) NOT NULL,
	detail TEXT,
	negative_ratio INTEGER,
	sentiment_score INTEGER,
	article_count INTEGER,
	is_read INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS analysis_results (
	id SERIAL NOT NULL,
	keyword VARCHAR(255) NOT NULL,
	analysis_type VARCHAR(50) NOT NULL,
	days INTEGER NOT NULL,
	result_json JSON NOT NULL,
	expired_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
	id SERIAL NOT NULL,
	actor_id INTEGER,
	actor_username VARCHAR(100) NOT NULL,
	action VARCHAR(50) NOT NULL,
	target_username VARCHAR(100),
	detail TEXT,
	created_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS authors (
	id SERIAL NOT NULL,
	username VARCHAR(100) NOT NULL,
	display_name VARCHAR(100),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id),
	UNIQUE (username)
);

CREATE TABLE IF NOT EXISTS plans (
	code VARCHAR(20) NOT NULL,
	display_name VARCHAR(50) NOT NULL,
	max_watch_keywords INTEGER NOT NULL,
	max_history_days INTEGER NOT NULL,
	allow_all_platforms INTEGER NOT NULL,
	monthly_qa_quota INTEGER NOT NULL,
	allow_export INTEGER NOT NULL,
	sort_order INTEGER NOT NULL,
	PRIMARY KEY (code)
);

CREATE TABLE IF NOT EXISTS platforms (
	id SERIAL NOT NULL,
	name VARCHAR(50) NOT NULL,
	display_name VARCHAR(100),
	base_url TEXT,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id),
	UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS settings (
	key VARCHAR(100) NOT NULL,
	value TEXT,
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (key)
);

CREATE TABLE IF NOT EXISTS users (
	id SERIAL NOT NULL,
	username VARCHAR(100) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	display_name VARCHAR(100),
	role VARCHAR(20) NOT NULL,
	avatar_emoji VARCHAR(16),
	avatar_color VARCHAR(16),
	is_active INTEGER NOT NULL,
	plan_code VARCHAR(20) NOT NULL,
	failed_login_count INTEGER NOT NULL,
	locked_until TIMESTAMP WITHOUT TIME ZONE,
	password_changed_at TIMESTAMP WITHOUT TIME ZONE,
	last_login_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS watch_keywords (
	id SERIAL NOT NULL,
	user_id INTEGER,
	keyword VARCHAR(255) NOT NULL,
	days INTEGER NOT NULL,
	enabled INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS boards (
	id SERIAL NOT NULL,
	platform_id INTEGER NOT NULL,
	name VARCHAR(100) NOT NULL,
	display_name VARCHAR(100),
	url TEXT,
	is_active INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id),
	FOREIGN KEY(platform_id) REFERENCES platforms (id)
);

CREATE TABLE IF NOT EXISTS usage_counters (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	period VARCHAR(7) NOT NULL,
	qa_count INTEGER NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS articles (
	id SERIAL NOT NULL,
	unique_id VARCHAR(64) NOT NULL,
	platform_id INTEGER NOT NULL,
	board_id INTEGER,
	author_id INTEGER,
	title TEXT NOT NULL,
	content TEXT,
	url TEXT,
	push_count INTEGER,
	sentiment VARCHAR(20),
	published_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id),
	UNIQUE (unique_id),
	FOREIGN KEY(board_id) REFERENCES boards (id),
	FOREIGN KEY(author_id) REFERENCES authors (id),
	FOREIGN KEY(platform_id) REFERENCES platforms (id)
);

CREATE TABLE IF NOT EXISTS crawl_logs (
	id SERIAL NOT NULL,
	platform_id INTEGER,
	board_id INTEGER,
	status VARCHAR(50) NOT NULL,
	new_count INTEGER,
	skipped_count INTEGER,
	filtered_count INTEGER,
	error_message TEXT,
	started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	finished_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(board_id) REFERENCES boards (id),
	FOREIGN KEY(platform_id) REFERENCES platforms (id)
);

CREATE TABLE IF NOT EXISTS comments (
	id SERIAL NOT NULL,
	article_id INTEGER NOT NULL,
	floor INTEGER,
	content TEXT NOT NULL,
	sentiment VARCHAR(20),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id),
	FOREIGN KEY(article_id) REFERENCES articles (id) ON DELETE CASCADE
);

ALTER TABLE articles ADD COLUMN IF NOT EXISTS sentiment VARCHAR(20);

ALTER TABLE boards ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1;

ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS days INTEGER NOT NULL DEFAULT 30;

ALTER TABLE crawl_logs ADD COLUMN IF NOT EXISTS filtered_count INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_alerts_id ON alerts (id);

CREATE INDEX IF NOT EXISTS ix_alerts_user_id ON alerts (user_id);

CREATE INDEX IF NOT EXISTS ix_analysis_results_id ON analysis_results (id);

CREATE INDEX IF NOT EXISTS ix_audit_logs_id ON audit_logs (id);

CREATE INDEX IF NOT EXISTS ix_authors_id ON authors (id);

CREATE INDEX IF NOT EXISTS ix_platforms_id ON platforms (id);

CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);

CREATE INDEX IF NOT EXISTS ix_watch_keywords_id ON watch_keywords (id);

CREATE INDEX IF NOT EXISTS ix_watch_keywords_user_id ON watch_keywords (user_id);

CREATE INDEX IF NOT EXISTS ix_boards_id ON boards (id);

CREATE INDEX IF NOT EXISTS ix_usage_counters_id ON usage_counters (id);

CREATE INDEX IF NOT EXISTS ix_usage_counters_period ON usage_counters (period);

CREATE INDEX IF NOT EXISTS ix_usage_counters_user_id ON usage_counters (user_id);

CREATE INDEX IF NOT EXISTS ix_articles_id ON articles (id);

CREATE INDEX IF NOT EXISTS ix_articles_sentiment ON articles (sentiment);

CREATE INDEX IF NOT EXISTS ix_crawl_logs_id ON crawl_logs (id);

CREATE INDEX IF NOT EXISTS ix_comments_article_id ON comments (article_id);

CREATE INDEX IF NOT EXISTS ix_comments_id ON comments (id);

CREATE INDEX IF NOT EXISTS ix_comments_sentiment ON comments (sentiment);
