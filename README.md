# ElastAlert Monitor

Sends an email when a service keeps failing, based on logs in our Elasticsearch.
Runs [ElastAlert2](https://elastalert2.readthedocs.io/en/latest/) in Docker. There is no custom code: everything is configured in YAML.

> **Status: not runnable yet.** The rules still contain `TODO` placeholders. See [What we still need](#what-we-still-need).

## What it alerts on

Every rule only looks at log documents where `isError: true`, and counts **each service separately**.

| Rule | File | Fires when | Next alert for the same service |
|---|---|---|---|
| Burst failures | [rules/01_burst_failures.yaml](rules/01_burst_failures.yaml) | 5 failures within 5 minutes | after 30 min |
| Recurring failures | [rules/02_recurring_failures.yaml](rules/02_recurring_failures.yaml) | 20 failures within 1 hour | after 1 hour |
| Daily threshold | [rules/03_daily_threshold.yaml](rules/03_daily_threshold.yaml) | 50 failures within the last 24 hours | after 24 hours |

These thresholds are starting guesses. We'll adjust them after testing against real data.
"Day" means the last 24 hours as a rolling window, not since midnight.

## How it works

```
 Docker host                                  Elasticsearch
┌─────────────────────────┐   HTTPS :9200   ┌────────────────────────────┐
│ elastalert container    │ ──────────────▶ │ search log index           │
│  every 1 minute:        │  user+password  │   (isError: true)          │
│  query → count → alert  │ ──────────────▶ │ write own state to         │
└───────────┬─────────────┘                 │   elastalert_status*       │
            │ SMTP                          └────────────────────────────┘
            ▼
      email recipients
```

- ElastAlert connects to the **Elasticsearch REST API, not Kibana**.
- It needs **read** access to the log index. It also needs **write** access to its own `elastalert_status*` indices, where it remembers what it already checked and already alerted on. This keeps it from sending duplicate alerts after a restart.
- Nothing is installed on the Elastic side.

## Project layout

```
docker-compose.yml        runs jertel/elastalert2
config.yaml               global settings (run every 1 min, writeback index, TLS options)
.env.example              Elasticsearch connection   → copy to .env
smtp_auth.example.yaml    mail account login         → copy to smtp_auth.yaml
rules/                    one YAML file per alert rule
```

`.env` and `smtp_auth.yaml` hold real credentials and are git-ignored. Never commit them.

## What we still need

### From a sample log (screenshot from Kibana Discover)
- [ ] **Index name / pattern**: replaces `TODO-INDEX-*` in all three rules
- [ ] **Service name field**: replaces every `TODO_SERVICE_FIELD` in all three rules
- [ ] **Timestamp field**: confirm it is `@timestamp`
- [ ] **`isError` type**: is it a boolean `true` or the string `"true"`? This decides how the filter is written.

### From the Elastic admin
- [ ] **Elasticsearch URL and port** (not the Kibana URL)
- [ ] **HTTPS?** If it uses a company/self-signed certificate, we need the **CA certificate file**
- [ ] **A dedicated user**, e.g. `elastalert`, with this role:

  | Resource | Privileges |
  |---|---|
  | log index (e.g. `app-logs-*`) | `read`, `view_index_metadata` |
  | `elastalert_status*` | `all` |
  | cluster | `monitor` |

### Mail
- [ ] **SMTP server host and port**, and whether it uses STARTTLS (587) or SSL (465)
- [ ] **Sender account**: address and password, or a relay that needs no login
- [ ] **Recipients**: who should get the alerts

### Decisions
- [ ] **Thresholds**: confirm or change 5/5 min, 20/1 h, and X = 50/day
- [ ] **Rule 2 meaning**: currently "keeps failing over a longer period (1 hour)". Change it if something else was meant.
- [ ] **Where it runs permanently**: an always-on server that can reach both Elasticsearch and the mail server

## Next steps

1. **Fill in the placeholders** in `rules/*.yaml` once the sample log is available.
2. **Check connectivity** from the machine that will run Docker:
   ```bash
   # should return JSON with cluster_name and version
   curl -u USER:PASS https://ELASTIC_HOST:9200

   # should return a count of failures
   curl -u USER:PASS "https://ELASTIC_HOST:9200/YOUR-INDEX-*/_count?q=isError:true"
   ```
   | Result | Meaning |
   |---|---|
   | Timeout | network or firewall problem, or wrong host/port |
   | `401` | wrong username or password |
   | SSL / certificate error | set `ca_certs` (or temporarily `verify_certs: false`) in `config.yaml` |
3. **Create the credential files:**
   ```bash
   cp .env.example .env                       # fill in ES_HOST, ES_PORT, ES_USERNAME, ES_PASSWORD
   cp smtp_auth.example.yaml smtp_auth.yaml   # fill in the mail account
   ```
   Also update `email`, `from_addr`, `smtp_host` and `smtp_port` in each rule.
4. **Dry-run each rule against real past data.** This prints what would have fired and sends no email:
   ```bash
   docker compose run --rm --entrypoint elastalert-test-rule elastalert \
     --config /opt/elastalert/config.yaml --days 1 /opt/elastalert/rules/01_burst_failures.yaml
   ```
   Repeat for `02_` and `03_`. Use `--days 7` to see a week.
5. **Tune thresholds** based on the dry-run results, so alerts mean something and don't flood inboxes.
6. **Start it:**
   ```bash
   docker compose up -d
   docker compose logs -f
   ```
7. **Later (optional):** add Slack/Teams alerts, a "since midnight" daily count, or per-service thresholds.

## Useful commands

```bash
docker compose ps            # is it running?
docker compose logs -f       # live logs
docker compose restart       # reload after editing rules or config
docker compose down          # stop
```
