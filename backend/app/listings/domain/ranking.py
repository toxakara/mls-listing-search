from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import exp

from app.listings.domain.models import Listing

SCORE_DECIMALS = 2


@dataclass(frozen=True)
class RelevanceScore:
    """All values are on a 0-100 scale, rounded to `SCORE_DECIMALS`.

    Results are sorted by the rounded value, so two listings that show the same score
    are ordered by the tie rule, not by a difference nobody can see.
    """

    relevance: float
    recency: float
    # None when the search has no target budget.
    budget: float | None

    @classmethod
    def rounded(cls, relevance: float, recency: float, budget: float | None) -> RelevanceScore:
        return cls(
            relevance=round(relevance, SCORE_DECIMALS),
            recency=round(recency, SCORE_DECIMALS),
            budget=None if budget is None else round(budget, SCORE_DECIMALS),
        )


@dataclass(frozen=True)
class BudgetRecencyRanking:
    """relevance = budget_weight * budget fit + (1 - budget_weight) * recency.

    Without a target budget, relevance is recency alone.
    """

    budget_weight: float = 0.7
    # Recency drops to ~37% (1/e) after this many days on the market.
    recency_decay_days: int = 90

    def score(self, listing: Listing, target_budget: float | None, today: date) -> RelevanceScore:
        recency = self._recency(listing.listed_date, today)
        if target_budget is None:
            return RelevanceScore.rounded(relevance=recency, recency=recency, budget=None)
        budget = self._budget_fit(listing.price, target_budget)
        relevance = self.budget_weight * budget + (1 - self.budget_weight) * recency
        return RelevanceScore.rounded(relevance=relevance, recency=recency, budget=budget)

    def _recency(self, listed_date: date, today: date) -> float:
        # A feed may send a future date; treat it as listed today.
        age_days = max(0, (today - listed_date).days)
        return 100 * exp(-age_days / self.recency_decay_days)

    @staticmethod
    def _budget_fit(price: float, target_budget: float) -> float:
        """100 at the exact budget, falling linearly to 0 at a 100% price difference."""
        return 100 * max(0.0, 1 - abs(price - target_budget) / target_budget)
