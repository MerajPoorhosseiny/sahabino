import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from configs import (
    BASE_BACKOFF,
    INITIAL_ADAPTIVE_DELAY,
    MAX_ADAPTIVE_DELAY,
    MAX_BACKOFF,
    MAX_RETRIES,
    MIN_ADAPTIVE_DELAY,
    TARGET_REVIEWS_COUNT,
    POLITE_JITTER_RANGE,
    REVIEWS_BATCH_SIZE,
    RATE_LIMIT_MARKERS,
)
from google_play_scraper import Sort, app, reviews
from google_play_scraper.exceptions import NotFoundError
from models import AppMetrics, Review

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class PlayStoreScraper:
    """Fetches app metrics and reviews from the Play Store with retry/backoff."""

    def __init__(
        self,
        fetch_app_details: Callable[..., Any] = app,
        fetch_reviews_page: Callable[..., Any] = reviews,
    ) -> None:
        """Accept the Play Store calls as injectable dependencies; the defaults hit the real store."""
        self.fetch_app_details = fetch_app_details
        self.fetch_reviews_page = fetch_reviews_page

        self.max_retries = MAX_RETRIES
        self.base_backoff = BASE_BACKOFF
        self.max_backoff = MAX_BACKOFF

        self.adaptive_delay = INITIAL_ADAPTIVE_DELAY
        self.min_delay = MIN_ADAPTIVE_DELAY
        self.max_delay = MAX_ADAPTIVE_DELAY


    def get_app_metrics(self, package_name: str) -> AppMetrics | None:
        for attempt in range(self.max_retries):
            try:
                raw_data = self.fetch_app_details(
                    package_name,
                    lang="en",
                    country="us",
                )

                scraped_at = datetime.now(UTC).isoformat()

                metrics = AppMetrics.from_scraped_payload(
                    raw_data, scraped_at
                )

                logger.info("Fetched app metrics for %s", package_name)
                return metrics

            except NotFoundError:
                logger.warning(
                    "App not found on Google Play: %s",
                    package_name,
                )
                return None

            except Exception:
                logger.exception(
                    "Failed fetching %s, attempt %d/%d",
                    package_name,
                    attempt + 1,
                    self.max_retries,
                )

                if attempt < self.max_retries - 1:
                    delay = min(
                        self.base_backoff * (2 ** attempt),
                        self.max_backoff,
                    )
                    time.sleep(delay + random.uniform(0, 0.5))

        return None

    
    def get_latest_reviews(
        self, package_name: str, count: int = TARGET_REVIEWS_COUNT
    ) -> list[dict[str, Any]]:
        """Fetch recent reviews in batches with retries and duplicate protection."""
        collected: dict[str, dict[str, Any]] = {}
        continuation_token = None

        while len(collected) < count:
            batch_size = min(REVIEWS_BATCH_SIZE, count - len(collected))
            result = None

            for attempt in range(self.max_retries):
                try:
                    result = self.fetch_reviews_page(
                        package_name,
                        lang="en",
                        country="us",
                        sort=Sort.NEWEST,
                        count=batch_size,
                        continuation_token=continuation_token,
                    )
                    self.adaptive_delay = max(
                        self.min_delay,
                        self.adaptive_delay - 0.05,
                    )
                    break

                except NotFoundError:
                    logger.warning(
                        "Reviews unavailable for %s", package_name
                    )
                    return list(collected.values())

                except Exception as exc:
                    logger.warning(
                        "Review fetch failed for %s (%d/%d): %s",
                        package_name,
                        attempt + 1,
                        self.max_retries,
                        exc,
                    )
                    if attempt == self.max_retries - 1:
                        return list(collected.values())

                    delay = min(
                        self.base_backoff * (2 ** attempt),
                        self.max_backoff,
                    )
                    time.sleep(delay + random.uniform(0, 0.5))

            if result is None:
                break

            raw_reviews, next_token = result

            if not raw_reviews:
                break

            scraped_at = datetime.now(UTC).isoformat()

            for raw_review in raw_reviews:
                review = Review.from_scraped_payload(
                    raw_review, scraped_at
                )
                if review is not None:
                    collected[review.review_id] = review.to_record()

            if next_token is None or next_token == continuation_token:
                break

            continuation_token = next_token
            time.sleep(
                self.adaptive_delay
                + random.uniform(*POLITE_JITTER_RANGE)
            )

        logger.info(
            "Fetched %d reviews for %s",
            len(collected),
            package_name,
        )
        return list(collected.values())
