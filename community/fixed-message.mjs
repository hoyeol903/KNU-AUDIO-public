import {json, Problem} from './api.mjs';

export async function fixedMessage(db) {
  if (!db) throw new Problem(503, '고정 멘트 저장 공간을 확인해 주세요.');
  const row = await db.prepare('SELECT text, updated_at FROM community_fixed_message WHERE id=1').first();
  if (!row) throw new Problem(503, '고정 멘트 초기 설정이 필요해요.');
  return {text: row.text, updatedAt: row.updated_at};
}

// 방송할 문장만 공개한다. 저장은 기존 관리자 인증을 통과해야 한다.
export async function publicFixedMessage(request, env) {
  try {
    if (request.method !== 'GET') return json({error:'조회만 가능한 주소예요.'}, 405);
    return json(await fixedMessage(env.COMMUNITY_DB));
  } catch (e) {
    return json({error:e instanceof Problem ? e.message : '고정 멘트를 읽지 못했어요.'}, e instanceof Problem ? e.status : 503);
  }
}
