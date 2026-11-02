# Error Dashboard

A small web page that shows **which services are failing today**, read live from our Elasticsearch.
It runs in Docker. Open `http://<server>:8080` in a browser.

> **Status: not runnable yet.** The index name and the service field are still `TODO` placeholders in `.env`. See [What we still need](#what-we-still-need).

## What the page shows

All numbers count log documents where `isError: true`, from **00:00 today** in the configured time zone.

| Section | Shows |
|---|---|
| Summary | total errors today · number of services with errors · number of services over the limit |
| Errors per hour | bar chart for today, 00:00–23:00. Hover a bar for the exact count. "Show as table" lists the same numbers. |
| Top 15 services | the 15 services with the most errors today, with bars for comparison |
| Over the limit | **every** service with more than 15 errors today |

The page reloads itself every 60 seconds. You can change 15 / 15 / 60 in `.env` (`TOP_N`, `DAILY_THRESHOLD`, `REFRESH_SECONDS`).

## How it works

```
 Browser ──HTTP :8080──▶ dashboard container ──HTTPS :9200──▶ Elasticsearch
                         (Python / Flask)       user+password   (read-only)
```

- Each time the page loads, the app sends **one aggregation query** to Elasticsearch: errors since midnight, grouped per service and per hour. It returns counts only, never the log documents themselves, so the query is cheap.
- It connects to the **Elasticsearch REST API, not Kibana**.
- It only **reads**. Nothing is written to Elasticsearch and nothing is installed there.
- If Elasticsearch can't be reached, the page shows the error message instead of numbers.

## Project layout

```
app/app.py                 Elasticsearch query + web server
app/templates/index.html   the page (layout, tables, chart)
app/requirements.txt       Python dependencies
Dockerfile                 builds the image
docker-compose.yml         runs it on port 8080
.env.example               all settings → copy to .env
```

`.env` holds the real password and is git-ignored. Never commit it.

## What we still need

### From a sample log (screenshot from Kibana Discover)
- [ ] **Index name / pattern** → `ES_INDEX`
- [ ] **Service name field** → `SERVICE_FIELD`. It must be a *keyword* field. If the field is text, use its `.keyword` version, e.g. `serviceName.keyword`.
- [ ] **Timestamp field** → `TIMESTAMP_FIELD`. Confirm it is `@timestamp`.
- [ ] **`isError` field** → `ERROR_FIELD`. Confirm the name and that it holds true/false.

### From the Elastic admin
- [ ] **Elasticsearch URL and port** (not the Kibana URL) → `ES_URL`
- [ ] **HTTPS?** If it uses a company/self-signed certificate, we need the **CA certificate file**.
- [ ] **A read-only user**, e.g. `dashboard`, with this role:

  | Resource | Privileges |
  |---|---|
  | log index (e.g. `app-logs-*`) | `read`, `view_index_metadata` |

### Decisions
- [ ] **Time zone** for "today": currently `Europe/Istanbul`
- [ ] **Limits**: top 15 and "more than 15 errors". Keep or change?
- [ ] **Where it runs**: a server that can reach Elasticsearch and that people can open in a browser

## Next steps

1. **Check connectivity** from the machine that will run Docker:
   ```bash
   # should return JSON with cluster_name and version
   curl -u USER:PASS https://ELASTIC_HOST:9200

   # should return a count of errors
   curl -u USER:PASS "https://ELASTIC_HOST:9200/YOUR-INDEX-*/_count?q=isError:true"
   ```
   | Result | Meaning |
   |---|---|
   | Timeout | network or firewall problem, or wrong host/port |
   | `401` | wrong username or password |
   | SSL / certificate error | use the CA file (see below), or set `ES_VERIFY_CERTS=false` for a quick test only |
2. **Create `.env`** and fill in the values:
   ```bash
   cp .env.example .env
   ```
   If you have a CA certificate, save it as `ca.crt` next to `docker-compose.yml`. Then uncomment the `volumes` lines in `docker-compose.yml` and set `ES_CA_CERT=/app/certs/ca.crt`.
3. **Build and start:**
   ```bash
   docker compose up -d --build
   ```
4. **Open** `http://localhost:8080`, or `http://<server-ip>:8080` from another machine.
5. **Compare with Kibana.** Check the numbers against a Kibana Discover search for `isError: true`, time range "Today".
6. **Later (optional):** a time-range picker (last 24 h / 7 days), errors per service over time, alerts again (email/Teams) on top of the same query.

## Useful commands

```bash
docker compose ps                 # is it running?
docker compose logs -f            # app logs
docker compose up -d --build      # rebuild after changing code or .env
docker compose down               # stop
curl http://localhost:8080/healthz
```
