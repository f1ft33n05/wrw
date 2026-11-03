from fastapi import HTTPException, Query


def pagination(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
) -> tuple[int, int]:
    return page, page_size


def paginated(items: list, page: int, page_size: int, total: int) -> dict:
    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
        },
    }
