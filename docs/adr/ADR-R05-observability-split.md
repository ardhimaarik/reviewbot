# ADR-R05: Observability Split — Reviewbot Exports, Pi 5 Monitors

**Date**: 2026-08-18
**Status**: Accepted
**Decider**: Ardhis

---

## Context

Reviewbot runs on MacBook M2 (compute node — sleep/wake). Prometheus + Grafana already run 24/7 on Raspberry Pi 5 (always-on bridge node). Two nodes are connected via Tailscale mesh.

Question: where does observability infrastructure live?

---

## Options Considered

**Option 1: Deploy Prometheus + Grafana on MacBook**
- Duplicates existing stack
- Dashboard goes down when MacBook sleeps
- Wastes ~500MB RAM on MacBook
- Two separate Prometheus instances = can't correlate with Pi metrics

**Option 2: Reviewbot exports metrics, Pi 5 scrapes + displays**
- Reviewbot Go service exposes `/metrics` on :8090
- Pi 5 Prometheus adds scrape target `100.114.34.102:8090` (Tailscale IP)
- Grafana dashboard lives on Pi 5 (:3001) — always accessible
- Zero new infrastructure

**Option 3: Push metrics to remote Prometheus (Pushgateway)**
- Works for batch jobs
- Overkill for a long-running service
- Adds Pushgateway dependency

---

## Decision

**Option 2: Split responsibilities.**

```
MacBook Reviewbot Go (:8090/metrics)
         ↓ Tailscale (100.114.34.102)
Pi 5 Prometheus (:9090) — scrapes every 15s
         ↓
Pi 5 Grafana (:3001) — dashboard always on
```

Pi 5 Prometheus config (`~/homelab/config/prometheus/prometheus.yml`):

```yaml
- job_name: 'reviewbot'
  scrape_interval: 15s
  scrape_timeout: 10s
  static_configs:
    - targets: ['100.114.34.102:8090']
      labels:
        instance: 'macbook-reviewbot'
```

---

## Consequences

**Positive:**
- Zero new infrastructure (reuse existing Pi 5 stack)
- Grafana dashboard accessible 24/7 from any LAN device (phone, tablet)
- Metrics visible even when MacBook asleep (historical data retained)
- Correlate Reviewbot metrics with system metrics (node-exporter, cAdvisor) in same Grafana

**Negative:**
- Metrics gap during MacBook sleep (scrape target will show "down")
- Tailscale must be running on both nodes for scraping to work
- If MacBook IP changes in Tailscale, scrape config needs update

**Accepted risk**: Metrics gap during sleep is acceptable — Reviewbot only processes PRs when MacBook is awake, so metric gaps are consistent with actual inactivity.

---

## Prometheus Retention

Pi 5 Prometheus retention: 15 days (set to protect microSD longevity).
Eval run history stored in Postgres (no retention limit) for long-term trend analysis.

---

## Interview Note

"I didn't spin up new monitoring infrastructure. I reused the Prometheus + Grafana stack already running on my Raspberry Pi. Reviewbot exposes metrics, Pi scrapes via Tailscale. The dashboard is always accessible from my phone even when MacBook sleeps. This is how you build infrastructure — compose what you have, don't duplicate."
