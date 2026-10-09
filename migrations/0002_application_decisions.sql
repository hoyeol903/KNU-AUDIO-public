-- 모집자가 신청을 수락·거절하고 사유를 남긴다. 양쪽 알림은 읽음 여부로 계산한다.
ALTER TABLE community_applications ADD COLUMN status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected'));
ALTER TABLE community_applications ADD COLUMN reason TEXT NOT NULL DEFAULT '';
ALTER TABLE community_applications ADD COLUMN decided_at INTEGER NOT NULL DEFAULT 0;
-- owner_seen: 모집자가 새 신청을 확인했는지. applicant_seen: 신청자가 수락·거절 결과를 확인했는지.
ALTER TABLE community_applications ADD COLUMN owner_seen INTEGER NOT NULL DEFAULT 0 CHECK(owner_seen IN (0, 1));
ALTER TABLE community_applications ADD COLUMN applicant_seen INTEGER NOT NULL DEFAULT 1 CHECK(applicant_seen IN (0, 1));
-- 이 기능 이전의 신청은 새 알림으로 띄우지 않는다.
UPDATE community_applications SET owner_seen = 1;
CREATE INDEX IF NOT EXISTS community_applications_applicant ON community_applications(applicant_hash, created_at DESC);
