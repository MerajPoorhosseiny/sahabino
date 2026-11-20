# Sahabino — Application & Network Analytics

Sahabino is a Python-based data collection and analytics project focused on Google Play application metrics, user reviews, and Android network traffic analysis. The project uses Python, PostgreSQL, Docker Compose, APScheduler, `google-play-scraper`, `dpkt`, pytest, and Metabase.

## Project Progress

| Day | Focus | Status |
| --- | --- | --- |
| 1 | Google Play metrics collection | Core implementation completed |
| 2 | Google Play reviews collection | Core implementation completed |
| 3 | Network traffic analysis | Core implementation and 12 captures completed |
| 4 | Metabase dashboards | Upcoming |
| 5 | Analytical questions and final reporting | Upcoming |

## Quick Start (Windows CMD)

### Prerequisites

- Git
- Docker Desktop with Docker Compose and a running Docker Engine
- Python 3.12 or later (only for local Python development; Docker can run the services independently)

### 1. Clone and locate the project

```cmd
git clone https://github.com/MerajPoorhosseiny/sahabino.git
cd sahabino
```

**Run the following commands from the directory containing `deployment`, `services`, `data`, and `utils`.** If the repository contains an inner `sahabino` folder, first run `cd sahabino` again. The expected Compose path from your current directory is `deployment\docker-compose.yml`.

### 2. Create your local environment file

`deployment/.env` is intentionally excluded from version control because it contains local database credentials. A safe template is provided as `deployment/.env.example`.

In Windows CMD:

```cmd
copy deployment\.env.example deployment\.env
```

Open `deployment/.env` in a text editor and **replace** `change_me_to_a_strong_password` with a unique local password. Do not commit or share this file.

The template defines `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`, `DB_BIND_IP`, `CRAWL_INTERVAL_HOURS`, and `METABASE_PORT`, matching `deployment/docker-compose.yml`.

**Existing installations:** Do not overwrite your working `.env`. Changing `POSTGRES_PASSWORD` in `.env` does not automatically change credentials already initialized inside a PostgreSQL Docker volume.

### 3. Start PostgreSQL, the crawler, and Metabase

```cmd
docker compose -f deployment\docker-compose.yml config --quiet
docker compose -f deployment\docker-compose.yml up -d --build postgres crawler metabase
docker compose -f deployment\docker-compose.yml ps
```

Docker Compose automatically reads `deployment/.env` because the Compose file is in `deployment`.

Open Metabase at **http://localhost:3000** (or the port set by `METABASE_PORT`). Complete first-run setup if necessary. When adding the Sahabino data source, choose PostgreSQL with host `postgres`, port `5432`, database `sahabino` (or your `POSTGRES_DB` value), and the configured database username and password.

The crawler runs on a schedule (`CRAWL_INTERVAL_HOURS`, default one hour). Docker Desktop and the host computer must be running for scheduled collection to continue.

### 4. Analyze PCAP captures

PCAP data is **not** committed to Git. Supply your own captures in this structure:

```text
data/pcap/
  Bale/
    messaging/
      bale_messaging_01.pcap
      bale_messaging_02.pcap
    upload/
      bale_upload_01.pcap
      bale_upload_02.pcap
    download/
      bale_download_01.pcap
      bale_download_02.pcap
  Eitaa/
    messaging/
      eitaa_messaging_01.pcap
      eitaa_messaging_02.pcap
    upload/
      eitaa_upload_01.pcap
      eitaa_upload_02.pcap
    download/
      eitaa_download_01.pcap
      eitaa_download_02.pcap
```

Folder names for applications must match active application titles in PostgreSQL. The analyzer discovers `.pcap` files under `data/pcap/<application>/<scenario>/` and avoids inserting duplicate captures using their SHA-256 hashes.

```cmd
docker compose -f deployment\docker-compose.yml build network_analyzer
docker compose -f deployment\docker-compose.yml run --rm network_analyzer
```

The analyzer writes results to the `network_metrics` table of the configured main database. This command runs the analyzer, **not** the destructive database tests.

### 5. Run automated tests safely

**Warning:** Database integration test fixtures truncate tables before and after tests. Never point tests at the main `sahabino` database.

Create/start the isolated database and build the test image:

```cmd
docker compose -f deployment\docker-compose.yml up -d postgres_test
docker compose -f deployment\docker-compose.yml build network_analyzer
```

Then run network tests with explicit test-only database settings:

```cmd
docker compose -f deployment\docker-compose.yml run --rm --no-deps -e POSTGRES_HOST=postgres_test -e POSTGRES_DB=sahabino_test network_analyzer python -m pytest tests/ -v
```

The command above assumes `POSTGRES_DB=sahabino` in `.env`, so the test database is named `sahabino_test`. If you use a different base database name, set `POSTGRES_DB` in this test command to `<your_database_name>_test` instead.

**Do not use** `docker compose down -v` on a working installation unless you deliberately intend to delete stored database volumes.

## Day 1 — Google Play Metrics Collection

### Completed work

- Configured the Python environment, Docker Desktop, PostgreSQL, and Metabase.
- Implemented Google Play scraping for eight application metrics.
- Initially configured 16 applications for collection; metrics were retrieved successfully for 13 of them under the tested locale settings.
- Added historical metric storage in PostgreSQL.
- Implemented hourly scheduled collection with APScheduler and Docker Compose.
- Verified database connectivity and initial stored metrics.

### Challenges and solutions

- **PostgreSQL authentication:** aligned the local environment settings with the initialized database credentials.
- **Docker image access:** used an available Docker image mirror for the PostgreSQL and Python base images.
- **Google Play availability:** Aparat, Filimo, and MyRightel returned `Not Found` for application metrics under the tested locale; their records were retained rather than inventing values.
- **Data safety:** added an isolated `postgres_test` service to keep destructive integration-test fixtures away from the main database.

### Outcome

The application metrics collector is operational with scheduled collection and timestamped PostgreSQL storage.

## Day 2 — Google Play Reviews Collection

### Completed work

- Implemented the `Review` data model, scraped-payload conversion, and database serialization.
- Added paginated review fetching using `google-play-scraper`, with continuation tokens, retry logic, request delays, and deduplication.
- Configured retrieval of up to 1,000 recent reviews per application per collection cycle.
- Added PostgreSQL upserts for reviews so repeated crawls do not create duplicate review IDs.
- Successfully retrieved reviews for all 16 initially configured applications.
- Verified a historical checkpoint of **14,033 unique reviews**; this number can increase as hourly collection continues.
- Passed **11 crawler-related automated tests** using the isolated test database.

### Challenges and solutions

- **Missing review implementation:** completed the model, scraper, and scheduled job integration.
- **Duplicate prevention:** used stable review IDs and database upserts.
- **Docker Desktop/WSL restart issues:** restored Docker and verified PostgreSQL without deleting volumes.
- **Transient startup/network errors:** confirmed readiness and retried collection after services recovered.
- **Uneven review availability:** stored only the reviews actually returned for each application.

### Outcome

The review collection pipeline runs on the scheduled crawler and persists real user reviews to PostgreSQL.

## Day 3 — Network Traffic Analysis

### Completed work

- Implemented packet parsing for PCAP and PCAPNG using `dpkt`, supporting Ethernet, raw IP, and Linux cooked capture link types in the current parser.
- Aggregated bidirectional TCP and UDP flows.
- Derived handshake RTT, retransmissions, zero-window events, TCP resets, transferred bytes, payload bytes, overhead ratio, and dominant server port.
- Added Bale (`ir.nasim`) and Eitaa (`ir.eitaa.messenger`) to the application dataset.
- Captured Android traffic using PCAPdroid.
- Collected and processed **12 real PCAP files**: two apps × three scenarios (`messaging`, `upload`, `download`) × two capture rounds.
- Stored capture results in PostgreSQL with SHA-256 hash-based deduplication.
- Passed **7 pipeline tests** and **3 network storage tests** in the isolated test database.

### Captures

| Scenario | Bale | Eitaa | Total |
| --- | ---: | ---: | ---: |
| Messaging (read and send text) | 2 | 2 | 4 |
| Upload | 2 | 2 | 4 |
| Download | 2 | 2 | 4 |
| **Total** | **6** | **6** | **12** |

### Preliminary measurements

The values below are averages across two captures per application and scenario, as returned by the existing analyzer and PostgreSQL queries.

| Scenario | Bale RTT (ms) | Eitaa RTT (ms) | Bale overhead (%) | Eitaa overhead (%) |
| --- | ---: | ---: | ---: | ---: |
| Messaging | 38.08 | 38.28 | 5.85 | 8.28 |
| Upload | 31.32 | 46.24 | 5.03 | 6.02 |
| Download | 43.03 | 60.54 | 0.89 | 1.87 |

No retransmissions were detected by the current heuristic in the 12 captures. This **does not** establish that no retransmissions occurred. TCP handshake RTT and retransmission detection are approximate; overhead is calculated as `(captured_bytes - application_payload_bytes) / captured_bytes`. The dominant server port is inferred from known service ports.

The capture sample is small and capture durations, transferred content, cache effects, and network conditions may differ. These preliminary measurements should not be treated as proof that one application is generally faster or more efficient.

### Outcome

The network analyzer successfully processed and stored 12 real captures in `network_metrics`, ready for visualization in Metabase.

## Technologies

- Python and `google-play-scraper` — application metrics and reviews
- APScheduler — scheduled crawling
- PostgreSQL — application, metric, review, and network data
- Docker Compose — service orchestration
- `dpkt` — PCAP/PCAPNG parsing
- pytest — automated tests
- Metabase — data exploration and visualization

## Current Limitations

- Google Play application metrics remain unavailable for three initially configured applications under the tested identifiers and locale settings.
- The crawler depends on a running Docker Engine and host computer.
- Transient database startup and DNS issues may still require improved resilience.
- Current TCP handshake RTT, retransmission detection, and server-port identification use approximations.
- The real PCAP dataset is small (two captures per application/scenario) and is not shipped in the Git repository.
- Metabase dashboards and final analytical reporting remain to be completed.

## Next Steps

- **Day 4:** Create Metabase dashboards for Google Play metrics, reviews, and network performance.
- **Day 5:** Answer the analytical questions and finalize the project report.
