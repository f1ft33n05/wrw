import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func

from config import APP_TIMEZONE
from database_models import DocumentSequence

NUMBER_WIDTH = 5
MAX_NUMBER = 10**NUMBER_WIDTH - 1


def _year_for(value: datetime | str | None, fallback_year: int) -> int:
    if value is None:
        return fallback_year
    try:
        parsed = (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, str)
            else value
        )
    except ValueError:
        return fallback_year
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(APP_TIMEZONE).year


def format_document_number(prefix: str, year: int, sequence: int) -> str:
    return f"{prefix}-{year}-{sequence:0{NUMBER_WIDTH}d}"


def display_document_number(
    number: str | None,
    prefix: str,
    created_at: datetime | str | None,
    record_id: int,
) -> str:
    year = _year_for(created_at, datetime.now(APP_TIMEZONE).year)
    if number:
        match = re.fullmatch(rf"{re.escape(prefix)}-(\d{{4}})-(\d+)", number)
        if match:
            return format_document_number(prefix, int(match.group(1)), int(match.group(2)))
    return format_document_number(prefix, year, record_id)


def next_document_number(
    db,
    model,
    field_name: str,
    prefix: str,
) -> str:
    year = datetime.now(APP_TIMEZONE).year
    year_prefix = f"{prefix}-{year}-"
    number_column = getattr(model, field_name)
    highest = 0
    legacy_highest_id = 0
    for number, record_id, created_at in (
        db.query(number_column, model.id, model.created_at).all()
    ):
        valid_number = False
        if number and number.startswith(year_prefix):
            suffix = number[len(year_prefix):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
                valid_number = True
        if not valid_number and _year_for(created_at, year) == year:
            legacy_highest_id = max(legacy_highest_id, record_id)

    baseline = max(highest, legacy_highest_id)
    dialect = db.get_bind().dialect.name
    sequence_table = DocumentSequence.__table__
    initial_value = baseline + 1
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        statement = insert(DocumentSequence).values(
            prefix=prefix,
            year=year,
            last_value=initial_value,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[sequence_table.c.prefix, sequence_table.c.year],
            set_={
                "last_value": func.max(
                    sequence_table.c.last_value, baseline
                )
                + 1
            },
        )
        next_number = db.execute(
            statement.returning(sequence_table.c.last_value)
        ).scalar_one()
    elif dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        statement = insert(DocumentSequence).values(
            prefix=prefix,
            year=year,
            last_value=initial_value,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[sequence_table.c.prefix, sequence_table.c.year],
            set_={
                "last_value": func.greatest(
                    sequence_table.c.last_value, baseline
                )
                + 1
            },
        )
        next_number = db.execute(
            statement.returning(sequence_table.c.last_value)
        ).scalar_one()
    else:
        sequence = (
            db.query(DocumentSequence)
            .filter_by(prefix=prefix, year=year)
            .with_for_update()
            .first()
        )
        if sequence is None:
            sequence = DocumentSequence(
                prefix=prefix,
                year=year,
                last_value=initial_value,
            )
            db.add(sequence)
        else:
            sequence.last_value = max(sequence.last_value, baseline) + 1
        db.flush()
        next_number = sequence.last_value

    if next_number > MAX_NUMBER:
        raise HTTPException(
            status_code=409,
            detail=f"The {prefix} numbering limit for {year} has been reached.",
        )
    return format_document_number(prefix, year, next_number)
