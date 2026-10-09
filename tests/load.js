// 소유/운영 권한이 있는 실제 배포 URL에서만 실행. 500 HTTP 이용자 부하 시험.
import http from 'k6/http';
import { check, sleep } from 'k6';
export const options = {
  stages: [{duration:'1m',target:100},{duration:'1m',target:500},{duration:'3m',target:500},{duration:'30s',target:0}],
  thresholds: {http_req_failed:['rate<0.01'], http_req_duration:['p(95)<2000'], checks:['rate>0.99']},
};
const base=(__ENV.BASE_URL || '').replace(/\/$/,'')+'/';
export default function () {
  if(!__ENV.BASE_URL) throw Error('본인 배포 주소 BASE_URL 필요');
  const result=http.get(base+'manifest.json');
  if(!check(result,{'manifest 200':r=>r.status===200})) return;
  const manifest=result.json();
  if(manifest.mode!=='slm-qwen3-tts') throw Error('실제 음성 배포본으로 부하 시험하세요');
  const role=Object.keys(manifest.voices)[0];
  const candidates=manifest.segments.filter(s=>s.audio[role]);
  if(!candidates.length) throw Error('음성 없음');
  const common=candidates.filter(s=>['greeting','weather','events','outro'].includes(s.kind));
  const personal=candidates.filter(s=>['notice','meal'].includes(s.kind));
  const queue=[...common,...(personal.length?[personal[__VU%personal.length]]:[])];
  http.get(base);
  if(manifest.bgm) check(http.get(base+manifest.bgm.path),{'music 200':r=>r.status===200});
  for(const segment of queue) {
    const audio=segment.audio[role];
    check(http.get(base+audio.url),{'audio 200':r=>r.status===200});
    sleep(Math.min(audio.duration_sec,20));
  }
}
