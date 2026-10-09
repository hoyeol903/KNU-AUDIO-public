(function (root) {
  'use strict';

  function validConfig(config) {
    if (!config || config.enabled !== true || typeof config.api_base !== 'string' || typeof config.site_key !== 'string') return false;
    try {
      var url = new URL(config.api_base);
      return url.protocol === 'https:' && !url.username && !url.password && !url.search && !url.hash &&
        /^[A-Za-z0-9_-]{10,128}$/.test(config.site_key);
    } catch (_) { return false; }
  }

  function loadTurnstile() {
    if (root.turnstile) return Promise.resolve(root.turnstile);
    if (root.__knuTurnstileLoading) return root.__knuTurnstileLoading;
    root.__knuTurnstileLoading = new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      script.onload = function () { root.turnstile ? resolve(root.turnstile) : reject(new Error('challenge_unavailable')); };
      script.onerror = function () { reject(new Error('challenge_unavailable')); };
      document.head.appendChild(script);
    });
    return root.__knuTurnstileLoading;
  }

  function turnstileToken(siteKey) {
    return loadTurnstile().then(function (turnstile) {
      return new Promise(function (resolve, reject) {
        var node = document.createElement('div'), widget;
        node.hidden = true;
        document.body.appendChild(node);
        var settled = false;
        function finish(error, token) {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          try { if (widget != null) turnstile.remove(widget); } catch (_) {}
          node.remove();
          error ? reject(error) : resolve(token);
        }
        var timer = setTimeout(function () { finish(new Error('challenge_timeout')); }, 15000);
        try {
          widget = turnstile.render(node, {
            sitekey: siteKey,
            size: 'invisible',
            execution: 'execute',
            action: 'onepass',
            callback: function (token) { finish(null, token); },
            'error-callback': function () { finish(new Error('challenge_failed')); },
            'timeout-callback': function () { finish(new Error('challenge_timeout')); },
            'expired-callback': function () { finish(new Error('challenge_expired')); }
          });
          turnstile.execute(widget);
        } catch (error) { finish(new Error('challenge_failed')); }
      });
    });
  }

  function selectionSignature(date, chapters) {
    return JSON.stringify([date, chapters.map(function (chapter) { return [chapter.id, chapter.s]; })]);
  }

  function create(options) {
    options = options || {};
    var config = options.config, ids = options.segmentIds;
    if (!validConfig(config)) return Promise.reject(new Error('service_unavailable'));
    if (typeof options.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(options.date) ||
        !Array.isArray(ids) || ids.length < 2 || ids.length > 60 ||
        ids.some(function (id) { return typeof id !== 'string' || !/^[A-Za-z0-9:_-]{1,128}$/.test(id); }) ||
        new Set(ids).size !== ids.length) return Promise.reject(new Error('selection_invalid'));
    var fetcher = options.fetch || root.fetch.bind(root), delay = options.delay || function (ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); };
    var now = options.now || Date.now, started = now(), maxWait = options.maxWaitMs || 180000;
    return (options.tokenProvider ? options.tokenProvider(config.site_key) : turnstileToken(config.site_key)).then(function (token) {
      if (typeof token !== 'string' || !token) throw new Error('challenge_failed');
      var base = config.api_base.replace(/\/+$/, '');
      return fetcher(base + '/v1/jobs', {
        method: 'POST', mode: 'cors', credentials: 'omit', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: options.date, segment_ids: ids, turnstile_token: token })
      }).then(function (response) {
        if (!response.ok) throw new Error('request_failed');
        return response.json();
      }).then(function (job) {
        if (!job || typeof job.job_id !== 'string' || !/^[A-Za-z0-9_-]{32,64}$/.test(job.job_id)) throw new Error('response_invalid');
        function completed(state, jobId) {
          return {
            audioUrl: base + '/v1/jobs/' + encodeURIComponent(jobId) + '/audio',
            durationSec: Number(state.duration_sec) || 0
          };
        }
        function poll() {
          if (now() - started >= maxWait) throw new Error('request_timeout');
          return fetcher(base + '/v1/jobs/' + encodeURIComponent(job.job_id), {
            method: 'GET', mode: 'cors', credentials: 'omit', cache: 'no-store'
          }).then(function (response) {
            if (!response.ok) throw new Error('request_failed');
            return response.json();
          }).then(function (state) {
            if (state.status === 'complete') return completed(state, job.job_id);
            if (state.status === 'failed' || state.status === 'expired') throw new Error(state.error || 'synthesis_failed');
            if (state.status !== 'queued' && state.status !== 'running') throw new Error('response_invalid');
            if (options.onStatus) options.onStatus(state.status);
            return delay(options.pollMs || 1500).then(poll);
          });
        }
        if (job.status === 'complete') return completed(job, job.job_id);
        if (job.status !== 'queued' && job.status !== 'running') throw new Error('response_invalid');
        return poll();
      });
    });
  }

  root.KnuOnePass = Object.freeze({ validConfig: validConfig, selectionSignature: selectionSignature, create: create });
})(typeof window !== 'undefined' ? window : globalThis);
