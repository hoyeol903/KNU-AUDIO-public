import http from 'node:http';
import {DatabaseSync} from 'node:sqlite';
import {mkdirSync, readFileSync} from 'node:fs';
import {dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {handleCommunity} from '../api.mjs';

export function createCommunityServer({databasePath, allowedOrigins, trustProxy = false}) {
  mkdirSync(dirname(databasePath), {recursive:true, mode:0o700});
  const sqlite = new DatabaseSync(databasePath);
  sqlite.exec('PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;');
  sqlite.exec(readFileSync(new URL('../../migrations/0001_community.sql', import.meta.url), 'utf8'));
  const db = {prepare(sql) {
    const statement = sqlite.prepare(sql); let args = [];
    return {
      bind(...values) { args = values; return this; },
      async first() { return statement.get(...args) || null; },
      async all() { return {results:statement.all(...args)}; },
      async run() { return statement.run(...args); },
    };
  }};
  const server = http.createServer(async (req, res) => {
    try {
      const path = new URL(req.url, 'http://localhost').pathname;
      if (path === '/health' && req.method === 'GET') {
        sqlite.prepare('SELECT 1').get();
        res.writeHead(200, {'Content-Type':'application/json', 'Cache-Control':'no-store'});
        return res.end('{"ok":true}');
      }
      if (!path.startsWith('/api/community/')) {
        res.writeHead(404, {'Content-Type':'application/json'});
        return res.end('{"error":"페이지를 찾을 수 없어요."}');
      }
      const body = await new Promise((resolve, reject) => {
        let size = 0; const parts = [];
        req.on('data', chunk => {
          size += chunk.length;
          if (size > 16000) { reject(Object.assign(new Error('body too large'), {status:413})); return; }
          parts.push(chunk);
        });
        req.on('end', () => resolve(Buffer.concat(parts)));
        req.on('error', reject);
        req.on('aborted', () => reject(new Error('aborted')));
      });
      const headers = new Headers();
      for (const [key,value] of Object.entries(req.headers)) {
        if (value !== undefined) headers.set(key, Array.isArray(value) ? value.join(', ') : value);
      }
      // Only the private Docker network's Caddy proxy may supply this header.
      // Ignore client-provided Cloudflare headers on Oracle.
      headers.set('CF-Connecting-IP', trustProxy ? (req.headers['x-knua-client-ip'] || req.socket.remoteAddress || '') : (req.socket.remoteAddress || ''));
      const request = new Request('http://localhost' + req.url, {
        method:req.method, headers,
        ...(!['GET','HEAD'].includes(req.method) && body.length ? {body} : {}),
      });
      const response = await handleCommunity(request, {COMMUNITY_DB:db, COMMUNITY_ALLOWED_ORIGINS:allowedOrigins});
      res.writeHead(response.status, Object.fromEntries(response.headers));
      res.end(Buffer.from(await response.arrayBuffer()));
    } catch (error) {
      if (!res.headersSent && !res.destroyed) {
        res.writeHead(error.status === 413 ? 413 : 500, {'Content-Type':'application/json', 'Cache-Control':'no-store'});
        res.end(JSON.stringify({error:error.status === 413 ? '입력 내용이 너무 길어요.' : '공유 서버에 연결하지 못했어요.'}));
      }
    }
  });
  server.requestTimeout = 20000;
  server.headersTimeout = 10000;
  server.on('close', () => sqlite.close());
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const server = createCommunityServer({
    databasePath:process.env.KNUA_DATABASE_PATH || '/var/lib/knua/community.sqlite',
    allowedOrigins:process.env.COMMUNITY_ALLOWED_ORIGINS || 'https://hoyeol903.github.io',
    trustProxy:process.env.KNUA_TRUST_PROXY === '1',
  });
  server.listen(Number(process.env.PORT || 8080), process.env.HOST || '127.0.0.1', () => console.log('KNUA community API ready'));
  for (const signal of ['SIGTERM','SIGINT']) process.on(signal, () => server.close());
}
