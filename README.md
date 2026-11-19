# Sahabino — Application & Network Analytics

Sahabino is a Python-based data collection and analytics project focused on Google Play application metrics, user reviews, and network traffic analysis.

The project uses Python, PostgreSQL, Docker Compose, APScheduler, and Metabase.

## Project Progress

| Day | Focus | Status |
|---|---|---|
| Day 1 | Google Play Metrics Collection | Core implementation completed |
| Day 2 | Google Play Reviews Collection | Core implementation completed |
| Day 3 | Network Traffic Analysis | Upcoming |
| Day 4 | Metabase Dashboards | Upcoming |
| Day 5 | Analytical Questions & Final Report | Upcoming |

---

## Day 1 — Google Play Metrics Collection

### Completed Tasks

- Configured the Python environment, Docker Desktop, PostgreSQL, and Metabase.
- Implemented a Google Play scraper to collect eight application metrics.
- Configured 16 applications for data collection.
- Successfully collected metrics from 13 accessible applications.
- Implemented hourly automated crawling using APScheduler and Docker Compose.
- Stored timestamped metrics in PostgreSQL to preserve historical data.
- Verified 27 initial metric records and inspected the results in Metabase.
- Updated the database initialization script and Git configuration.

### Challenges & Solutions

**1. PostgreSQL authentication errors**

The initial database credentials did not match the running PostgreSQL configuration.

**Solution:** Corrected the database credentials and environment variables to establish a successful connection.

**2. Docker image download and startup issues**

Docker image availability and connectivity caused setup difficulties.

**Solution:** Used accessible Docker image mirrors and configured Docker Compose to run the required services.

**3. Unavailable Google Play applications**

Aparat, Filimo, and MyRightel returned `Not Found` when retrieving application metrics.

**Solution:** Preserved their entries in the application list, continued collecting available application metrics, and documented the limitation for mentor clarification.

**4. Test database safety**

Some automated tests clear database tables before and after execution, creating a risk to collected data.

**Solution:** Configured a separate PostgreSQL test service and ran database integration tests against `sahabino_test`.

### Day 1 Outcome

The application metrics pipeline became operational, with hourly scheduled collection, PostgreSQL storage, and Metabase access.

---

## Day 2 — Google Play Reviews Collection

### Completed Tasks

- Implemented the `Review` model and payload conversion methods.
- Developed paginated review collection using `google-play-scraper`.
- Configured collection of up to 1,000 recent reviews per application per cycle.
- Added retries, request delays, and continuation-token handling.
- Implemented review persistence using database upserts.
- Successfully collected reviews for all 16 applications.
- Stored 14,033 unique reviews after subsequent collection cycles.
- Verified review IDs, timestamps, scores, and content in PostgreSQL.
- Passed 11 automated tests covering models, storage, and crawler operations.
- Verified the collected reviews through Metabase.

### Challenges & Solutions

**1. Incomplete review implementation**

The original review model and scraper methods were not implemented.

**Solution:** Added review payload conversion, database record serialization, and paginated review fetching.

**2. Duplicate review prevention**

Repeated hourly crawling could retrieve the same reviews multiple times.

**Solution:** Used unique review IDs and PostgreSQL upsert operations to update existing reviews rather than insert duplicates.

**3. Docker Desktop and WSL startup failure**

Docker Desktop temporarily stopped working because the WSL backend failed to start correctly.

**Solution:** Restarted Windows and restored Docker Engine without deleting PostgreSQL volumes or previously collected data.

**4. Temporary database and network errors**

After Docker restarted, the crawler initially attempted to connect while PostgreSQL was still starting. A later request also encountered a temporary DNS resolution failure.

**Solution:** Verified database connectivity after startup. The scraper's retry logic successfully recovered from the transient network failure during a subsequent crawl.

**5. Different review availability across applications**

Some applications returned fewer than 1,000 reviews, while others returned the full requested amount.

**Solution:** Stored the available reviews without inventing or duplicating records.

### Day 2 Outcome

The review collection pipeline successfully retrieved and stored real user reviews for all 16 configured applications. The latest verified database count was **14,033 unique reviews**.

---

## Technologies Used

- **Python:** Data collection and processing
- **google-play-scraper:** Google Play metrics and reviews
- **APScheduler:** Hourly automated execution
- **PostgreSQL:** Persistent data storage
- **Docker Compose:** Containerized services
- **pytest:** Automated testing
- **Metabase:** Data exploration and visualization

## Current Limitations

- Google Play metrics remain unavailable for three configured applications under the current identifiers and locale settings.
- Automatic collection requires Docker Engine and the host computer to remain running.
- Startup readiness and temporary network failures should receive further resilience improvements.
- Network PCAP analysis and final dashboards are planned for the next project phases.

## Next Steps

**Day 3:** Capture and analyze network traffic using PCAP files.

**Day 4:** Build analytical dashboards in Metabase.

**Day 5:** Answer the required analytical questions and finalize the project report.