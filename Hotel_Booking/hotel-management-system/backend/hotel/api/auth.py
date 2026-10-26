from datetime import datetime, timedelta, timezone
from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import AnonRateThrottle
from bson import ObjectId
from hotel.db import collection
from hotel.authentication import issue_token
from hotel.serializers import RegisterSerializer, LoginSerializer
from hotel.serialization import document
from hotel.encryption import protect_guest_fields

class LoginThrottle(AnonRateThrottle): scope = 'login'

def account(user):
    return {'id': str(user['_id']), 'name': user.get('name',''), 'email': user['email'], 'phone':user.get('phone',''), 'role': user['role'], 'guestId': str(user['guestId']) if user.get('guestId') else None}

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data); serializer.is_valid(raise_exception=True); values=serializer.validated_data
    email=values['email'].lower()
    if collection('users').find_one({'email':email}): return Response({'message':'An account with this email already exists.'},status=409)
    guest={'firstName':values['firstName'],'lastName':values.get('lastName',''),'email':email,'phone':values['phone'],'address':'','idProofType':'Passport','idProofNo':f'WEB-{ObjectId()}','registeredOn':datetime.now(timezone.utc)}
    guest_id=collection('guests').insert_one(protect_guest_fields(guest)).inserted_id
    user={'name':f"{values['firstName']} {values.get('lastName','')}".strip(),'email':email,'phone':values['phone'],'passwordHash':make_password(values['password']),'role':'guest','active':True,'guestId':guest_id,'createdAt':datetime.now(timezone.utc)}
    user['_id']=collection('users').insert_one(user).inserted_id
    return Response({'access':issue_token(user),'user':account(user)},status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    serializer=LoginSerializer(data=request.data);serializer.is_valid(raise_exception=True);values=serializer.validated_data
    user=collection('users').find_one({'email':values['email'].lower(),'active':True})
    if not user or not check_password(values['password'],user.get('passwordHash','')):
        collection('auth_events').insert_one({'email':values['email'].lower(),'ip':request.META.get('REMOTE_ADDR'),'event':'login_failed','createdAt':datetime.now(timezone.utc)})
        return Response({'message':'Email or password is incorrect.'},status=401)
    token=issue_token(user)
    return Response({'access':token,'expiresIn':settings.JWT_LIFETIME_SECONDS,'user':account(user)})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    import jwt
    from hotel.serialization import oid
    claims=jwt.decode(request.auth,settings.JWT_SECRET,algorithms=['HS256'])
    collection('revoked_tokens').insert_one({'jti':claims['jti'],'expiresAt':datetime.fromtimestamp(claims['exp'],timezone.utc)})
    return Response({'message':'Signed out.'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refresh_token(request):
    user=collection('users').find_one({'_id':ObjectId(request.user.id),'active':True})
    return Response({'access':issue_token(user),'expiresIn':settings.JWT_LIFETIME_SECONDS})

@api_view(['GET','PATCH'])
@permission_classes([IsAuthenticated])
def me(request):
    user=collection('users').find_one({'_id':ObjectId(request.user.id)})
    if request.method=='GET': return Response(account(user))
    allowed={'name','phone','preferences'}
    updates={k:v for k,v in request.data.items() if k in allowed}
    if updates:
        collection('users').update_one({'_id':user['_id']},{'$set':updates})
        if user.get('guestId'):
            guest_updates={}
            if 'name' in updates:
                parts=updates['name'].strip().split(' ',1);guest_updates.update({'firstName':parts[0],'lastName':parts[1] if len(parts)>1 else ''})
            if 'phone' in updates:guest_updates['phone']=updates['phone']
            if guest_updates:collection('guests').update_one({'_id':user['guestId']},{'$set':guest_updates})
    return Response(account(collection('users').find_one({'_id':user['_id']})))
