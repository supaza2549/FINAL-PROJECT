"""Search the date as displayed to the shop, including partial input."""
from datetime import datetime,timezone,timedelta
def date_matches(value,created_at):
    value=value.strip()
    if not value:return True
    stamp=datetime.fromisoformat(str(created_at).replace('Z','+00:00'))
    if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
    stamp=stamp.astimezone(timezone(timedelta(hours=7)))
    for pattern in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y'):
        try:
            parsed=datetime.strptime(value,pattern)
            if parsed.year>2400:parsed=parsed.replace(year=parsed.year-543)
            return parsed.date()==stamp.date()
        except ValueError:pass
    return any(text.startswith(value) for text in (stamp.strftime('%Y-%m-%d'),stamp.strftime('%d/%m/%Y'),stamp.strftime('%d-%m-%Y')))
