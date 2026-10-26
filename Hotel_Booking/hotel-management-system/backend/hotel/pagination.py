from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from hotel.serialization import document

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        self._mongo_rows = list(queryset)
        self.request = request
        try: size = min(max(int(request.query_params.get('page_size', self.page_size)), 1), self.max_page_size)
        except (TypeError, ValueError): size = self.page_size
        try: page = max(int(request.query_params.get('page', 1)), 1)
        except (TypeError, ValueError): page = 1
        self.count = len(self._mongo_rows)
        self.page_rows = self._mongo_rows[(page - 1) * size:page * size]
        self.page_number = page
        self.page_size = size
        return self.page_rows

    def get_paginated_response(self, data):
        return Response({'count': self.count, 'page': self.page_number, 'pageSize': self.page_size, 'results': data})

def paged(request, rows):
    paginator = StandardPagination()
    result = paginator.paginate_queryset(rows, request)
    return paginator.get_paginated_response([row if isinstance(row, dict) and 'id' in row else document(row) for row in result])
