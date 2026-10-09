-- 기존 모집글과 신청은 보존한다. 숨김은 삭제·모집 마감과 별개다.
ALTER TABLE community_posts ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0 CHECK(hidden IN (0, 1));
CREATE INDEX IF NOT EXISTS community_posts_visible ON community_posts(hidden, closed, created_at DESC, id DESC);
CREATE TABLE IF NOT EXISTS community_reports (
  post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
  reporter_hash TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY(post_id, reporter_hash)
);
CREATE INDEX IF NOT EXISTS community_reports_date ON community_reports(created_at DESC);
CREATE TABLE IF NOT EXISTS community_admin_sessions (
  token_hash TEXT PRIMARY KEY,
  credential_hash TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS community_admin_session_expiry ON community_admin_sessions(expires_at);
