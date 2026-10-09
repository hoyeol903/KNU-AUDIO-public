import {handleCommunity} from './api.mjs';
import {handleAdmin} from './admin.mjs';

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === '/admin' || path.startsWith('/admin/')) return handleAdmin(request, env);
    if (!path.startsWith('/api/community/')) {
      return new Response(JSON.stringify({error: '페이지를 찾을 수 없어요.'}), {
        status: 404,
        headers: {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'},
      });
    }
    return handleCommunity(request, env);
  },
};
