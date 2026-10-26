from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from hotel.db import collection
from hotel.serialization import document

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    try:
        collection('guests').database.client.admin.command('ping')
        return Response({'status':'ok','database':'connected'})
    except Exception:
        return Response({'status':'error','database':'unavailable'},status=503)
