from datetime import date, timedelta


AGING_BUCKET_LABELS = {
    'aging_0_7_days': '0-7 Days',
    'aging_8_14_days': '8-14 Days',
    'aging_15_30_days': '15-30 Days',
    'aging_31_plus_days': '31+ Days',
}


def ww_range_to_dates(begin_ww: str, end_ww: str) -> tuple[date, date]:
    begin = ww_to_monday(begin_ww)
    end = ww_to_monday(end_ww) + timedelta(days=6)
    return begin, end


def provider_query_range_to_dates(query) -> tuple[date, date]:
    range_mode = provider_query_range_mode(query)
    if range_mode == 'date':
        begin = iso_date_value(query.begin_date, 'begin_date')
        end = iso_date_value(query.end_date, 'end_date')
        if begin > end:
            raise ValueError('begin_date must be earlier than or equal to end_date.')
        return begin, end
    if range_mode == 'ww':
        return ww_range_to_dates(query.begin_ww, query.end_ww)
    raise ValueError('range_mode must be ww or date.')


def provider_query_range_mode(query) -> str:
    return (query.range_mode or 'ww').strip().lower()


def iso_date_value(value: str, field_name: str) -> date:
    if not value:
        raise ValueError(f'{field_name} is required when range_mode=date.')
    return date.fromisoformat(value[:10])


def ww_to_monday(value: str) -> date:
    normalized = value.strip()
    if len(normalized) != 6 or normalized[2:4].upper() != 'WW':
        raise ValueError('WW values must use YYWWNN format.')
    year = 2000 + int(normalized[:2])
    week = int(normalized[4:])
    return date.fromisocalendar(year, week, 1)
