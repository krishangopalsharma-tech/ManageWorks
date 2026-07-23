from rest_framework.pagination import PageNumberPagination


class ProgressPageNumberPagination(PageNumberPagination):
    """Shared pagination for the Item Progress / Location Progress endpoints —
    the only views in the app expected to return thousands of rows when a
    user selects many/all works at once."""
    page_size = 200
    page_size_query_param = 'page_size'
    max_page_size = 500
