from rest_framework.views import exception_handler
from rest_framework.response import Response
from pymongo.errors import DuplicateKeyError, PyMongoError

def api_exception_handler(exc, context):
    if isinstance(exc,DuplicateKeyError):
        return Response({'success':False,'message':'A record already uses that unique value.'},status=409)
    if isinstance(exc,PyMongoError):
        return Response({'success':False,'message':'The database request could not be completed.'},status=503)
    response = exception_handler(exc, context)
    if response is None:
        return Response({'success': False, 'message': 'Unexpected server error.'}, status=500)
    detail = response.data
    if isinstance(detail,str): message=detail
    elif isinstance(detail,dict):
        parts=[]
        for key,value in detail.items():
            if isinstance(value,list): text=' '.join(str(x) for x in value)
            else: text=str(value)
            parts.append(f'{key}: {text}')
        message='; '.join(parts) or 'Request could not be completed.'
    else: message='Request could not be completed.'
    response.data = {'success': False, 'message': message, 'errors': detail if isinstance(detail, dict) else {}}
    return response
