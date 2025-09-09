/* scripts/consul-register.cjs */
const Consul = require('consul');

// ---- Config (env overrides optional) ----
const CONSUL_HOST = process.env.CONSUL_HOST || 'host.docker.internal'; // Consul UI/API exposed on host:8500
const CONSUL_PORT = Number(process.env.CONSUL_PORT || 8500);

// Next.js dev runs on the host; Consul is in a Docker container.
// From inside the Consul container, the host is reachable as host.docker.internal (on Docker Desktop).
const SERVICE_NAME = process.env.CONSUL_SERVICE_NAME || 'osss-web';
const SERVICE_ID = process.env.CONSUL_SERVICE_ID || `${SERVICE_NAME}-dev`;
const SERVICE_ADDR = process.env.CONSUL_SERVICE_ADDR || 'host.docker.internal';
const SERVICE_PORT = Number(process.env.CONSUL_SERVICE_PORT || 3000);
const HEALTH_PATH  = process.env.CONSUL_HEALTH_PATH || '/';

const consul = new Consul({
  host: CONSUL_HOST,
  port: CONSUL_PORT,
  promisify: true,
});

async function main() {
  try {
    // idempotent-ish: try to deregister first (ignore errors)
    try { await consul.agent.service.deregister(SERVICE_ID); } catch (_) {}

    await consul.agent.service.register({
      name: SERVICE_NAME,
      id: SERVICE_ID,
      address: SERVICE_ADDR,
      port: SERVICE_PORT,
      tags: ['nextjs', 'dev'],
      check: {
        http: `http://${SERVICE_ADDR}:${SERVICE_PORT}${HEALTH_PATH}`,
        interval: '10s',
        timeout: '2s',
        DeregisterCriticalServiceAfter: '1m',
      },
    });

    // Keep the process alive while Next.js runs (this file is backgrounded by & in your script)
    console.log(`[consul] registered ${SERVICE_NAME} → ${SERVICE_ADDR}:${SERVICE_PORT}`);
    const cleanup = async () => {
      try {
        await consul.agent.service.deregister(SERVICE_ID);
        console.log(`[consul] deregistered ${SERVICE_ID}`);
      } catch (e) {
        console.warn('[consul] deregister failed:', e.message || e);
      } finally {
        process.exit(0);
      }
    };
    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);
    process.on('exit', cleanup);

    // noop timer to keep event loop alive
    setInterval(() => {}, 1 << 30);
  } catch (e) {
    console.error('[consul] register error:', e && e.message ? e.message : e);
    process.exit(1);
  }
}

main();
