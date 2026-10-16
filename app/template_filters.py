from datetime import datetime


# REVIEW: Jinja2 template filter registration for localized MWK currency and ISO date formatting.
def register_template_filters(app):
    @app.template_filter("currency")
    def format_currency(value):
        try:
            return f"MWK {float(value):,.2f}"
        except (ValueError, TypeError):
            return "MWK 0.00"

    @app.template_filter("datetime")
    def format_datetime(value, format="%Y-%m-%d %H:%M"):
        if not value:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime(format)

