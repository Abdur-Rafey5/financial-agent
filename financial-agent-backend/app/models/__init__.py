"""
Models package — import all models here so Alembic and SQLAlchemy
can discover them for migration auto-generation.
"""

from app.models.user import User, UserProfile, UserCategory  # noqa: F401
from app.models.income import (  # noqa: F401
    IncomeRecord,
    IncomeCategory,
    IncomeType,
    IncomeFrequency,
)
from app.models.expense import ExpenseRecord, ExpenseCategory  # noqa: F401
from app.models.budget import Budget, BudgetCategory, BudgetPeriod  # noqa: F401
from app.models.goal import (  # noqa: F401
    FinancialGoal,
    GoalContribution,
    GoalStatus,
)
from app.models.business import (  # noqa: F401
    Business,
    BusinessScenario,
    MarketDataSnapshot,
)
from app.models.ai import (  # noqa: F401
    AIConversation,
    AIMessage,
    AIRecommendation,
    AgentEvent,
    MessageRole,
    RecommendationType,
    RecommendationPriority,
)
