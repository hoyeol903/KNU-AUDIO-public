PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS community_posts (
  id TEXT PRIMARY KEY,
  owner_hash TEXT NOT NULL,
  category TEXT NOT NULL CHECK(category IN ('dating', 'study', 'club')),
  payload TEXT NOT NULL,
  closed INTEGER NOT NULL DEFAULT 0 CHECK(closed IN (0, 1)),
  application_count INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS community_posts_category_date ON community_posts(closed, category, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS community_posts_date ON community_posts(closed, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS community_posts_owner_date ON community_posts(owner_hash, created_at DESC, id DESC);
CREATE TABLE IF NOT EXISTS community_applications (
  post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
  applicant_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  team TEXT NOT NULL,
  message TEXT NOT NULL,
  contact TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY(post_id, applicant_hash)
);
CREATE TRIGGER IF NOT EXISTS community_application_added AFTER INSERT ON community_applications BEGIN
  UPDATE community_posts SET application_count=application_count+1 WHERE id=NEW.post_id;
END;
CREATE TRIGGER IF NOT EXISTS community_application_removed AFTER DELETE ON community_applications BEGIN
  UPDATE community_posts SET application_count=application_count-1 WHERE id=OLD.post_id;
END;
CREATE TABLE IF NOT EXISTS community_limits (key TEXT PRIMARY KEY, day TEXT NOT NULL, count INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS community_limits_day ON community_limits(day);
