from dataclasses import dataclass
from enum import Enum

class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"

@dataclass
class PlanLimits:
    repos: int
    requests_per_day: int
    requests_per_month: int
    max_tokens_per_request: int
    team_members: int
    features: list[str]

PLAN_LIMITS: dict[PlanTier, PlanLimits] = {
    PlanTier.FREE: PlanLimits(
        repos=1,
        requests_per_day=100,
        requests_per_month=1000,
        max_tokens_per_request=4000,
        team_members=1,
        features=["basic_search", "graph_view"]
    ),
    PlanTier.PRO: PlanLimits(
        repos=5,
        requests_per_day=1000,
        requests_per_month=10000,
        max_tokens_per_request=16000,
        team_members=1,
        features=["semantic_search", "token_budgeting", "impact_analysis", "api_access"]
    ),
    PlanTier.TEAM: PlanLimits(
        repos=20,
        requests_per_day=5000,
        requests_per_month=50000,
        max_tokens_per_request=32000,
        team_members=10,
        features=["semantic_search", "token_budgeting", "impact_analysis", 
                  "api_access", "team_management", "priority_support"]
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        repos=-1,  # unlimited
        requests_per_day=-1,
        requests_per_month=-1,
        max_tokens_per_request=100000,
        team_members=-1,
        features=["all", "sso", "audit_logs", "sla", "dedicated_support"]
    ),
}

# Stripe Price IDs
STRIPE_PRICES = {
    PlanTier.PRO: "price_pro_monthly",
    PlanTier.TEAM: "price_team_monthly",
}