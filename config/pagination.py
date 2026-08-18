from rest_framework.pagination import CursorPagination


class DefaultCursorPagination(CursorPagination):
    """
    Cursor pagination everywhere, deliberately not offset pagination:
    offset-based pages drift when rows are inserted mid-scroll (very likely
    on a live feed), and OFFSET N gets slower the deeper you page. A cursor
    keyed on an indexed column is stable and O(page size).
    """

    page_size = 20
    ordering = "-created_at"
