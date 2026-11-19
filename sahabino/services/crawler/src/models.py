from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Optional

from configs import FALLBACK_VERSION_LABEL



@dataclass(frozen=True)
class Review:
    """One Google Play review, ready to be stored in PostgreSQL."""

    review_id: str
    user_name: str | None
    score: int | None
    thumbs_up_count: int
    content: str
    review_at: str | None
    scraped_at: str

    @classmethod
    def from_scraped_payload(
        cls, payload: dict[str, Any], scraped_at: str
    ) -> "Review | None":
        # A review without a unique ID cannot be safely stored or updated.
        review_id = payload.get("reviewId")
        if not review_id:
            return None

        # Google Play returns the review date as a datetime object.
        review_date = payload.get("at")
        review_at = None

        if isinstance(review_date, datetime):
            if review_date.tzinfo is None:
                review_date = review_date.replace(tzinfo=UTC)
            review_at = review_date.astimezone(UTC).isoformat()

        return cls(
            review_id=str(review_id),
            user_name=payload.get("userName"),
            score=payload.get("score"),
            thumbs_up_count=int(payload.get("thumbsUpCount") or 0),
            content=payload.get("content") or "",
            review_at=review_at,
            scraped_at=scraped_at,
        )

    def to_record(self) -> dict[str, Any]:
        # Match the column names expected by the database layer.
        return {
            "review_id": self.review_id,
            "user_name": self.user_name,
            "score": self.score,
            "thumbs_up_count": self.thumbs_up_count,
            "content": self.content,
            "review_at": self.review_at,
            "scraped_at": self.scraped_at,
        }



@dataclass(frozen=True)
class AppMetrics:
    """One app's store metrics, translated from the raw scraper payload into the app_metrics-table shape."""

    min_installs: int | None
    real_installs: int | None
    score: float
    ratings: int | None
    reviews_count: int | None
    version: str
    ad_supported: bool
    store_updated_at: str | None
    scraped_at: str

    @classmethod
    def from_scraped_payload(cls, payload: dict[str, Any], scraped_at: str) -> "AppMetrics":
        updated = payload.get("updated")

        store_updated_at = None
        if updated is not None:
            if isinstance(updated, datetime):
                store_updated_at = updated.astimezone(UTC).isoformat()
            elif isinstance(updated, (int, float)):
                store_updated_at = datetime.fromtimestamp(
                    updated, tz=UTC
                ).isoformat()

        return cls(
            min_installs=payload.get("minInstalls"),
            real_installs=payload.get("realInstalls"),
            score=round(float(payload.get("score") or 0.0), 2),
            ratings=payload.get("ratings"),
            reviews_count=payload.get("reviews"),
            version=payload.get("version") or FALLBACK_VERSION_LABEL,
            ad_supported=bool(payload.get("adSupported", False)),
            store_updated_at=store_updated_at,
            scraped_at=scraped_at,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "min_installs": self.min_installs,
            "real_installs": self.real_installs,
            "score": self.score,
            "ratings": self.ratings,
            "reviews_count": self.reviews_count,
            "version": self.version,
            "ad_supported": self.ad_supported,
            "store_updated_at": self.store_updated_at,
            "scraped_at": self.scraped_at,
        }