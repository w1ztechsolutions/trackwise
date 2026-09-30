"""Business-scoped accounting period close controls."""

from datetime import date, datetime

from app.models.accounting import Business


class PeriodClosedError(Exception):
    """Raised when a financial transaction affects a closed accounting date."""


def as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def assert_period_open(business_id, transaction_date):
    business = Business.query.filter_by(id=business_id).first()
    if business and business.last_closed_period_date:
        transaction_day = as_date(transaction_date)
        if transaction_day <= business.last_closed_period_date:
            raise PeriodClosedError(
                f"Accounting period is closed through "
                f"{business.last_closed_period_date.isoformat()}; "
                f"transactions must be dated after that day."
            )


def close_period(business_id, close_through):
    if close_through > date.today():
        raise ValueError("A period cannot be closed beyond today's date")

    business = Business.query.filter_by(id=business_id).with_for_update().first()
    if business is None:
        raise ValueError("Business not found")
    if (
        business.last_closed_period_date is not None
        and close_through <= business.last_closed_period_date
    ):
        raise ValueError("The close-through date must be later than the current close date")

    business.last_closed_period_date = close_through
