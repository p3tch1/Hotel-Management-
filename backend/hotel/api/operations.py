from datetime import datetime, time, timezone
import csv
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.http import HttpResponse
from hotel.db import collection
from hotel.serialization import document, documents, oid
from hotel.encryption import protect_guest_fields
from hotel.pagination import paged
from hotel.permissions import IsStaff, IsManager, IsStaffOrGuest
from hotel.serializers import BookingSerializer, RoomSerializer, RoomTypeSerializer, ServiceCatalogSerializer, ServiceRequestSerializer, PaymentSerializer, StatusSerializer
from hotel.services.bookings import create_booking, bill_for
from hotel.services.workflows import booking_transition_allowed, service_request_transition_allowed

def audit(actor, action, entity, entity_id, summary=None):
    collection('audit_logs').insert_one({'actorId':ObjectId(actor.id),'actorEmail':actor.email,'actorRole':actor.role,'action':action,'entity':entity,'entityId':str(entity_id),'summary':summary or {},'createdAt':datetime.now(timezone.utc)})

def role_denied(request, roles):
    return request.user.role not in roles

def expand_booking(b):
    row=document(b)
    row.pop('createdBy',None)
    guest=collection('guests').find_one({'_id':b.get('guestId')}) if b.get('guestId') else None
    room=collection('rooms').find_one({'_id':b.get('roomId')}) if b.get('roomId') else None
    if guest: row['guestId']=document(guest)
    if room:
        room_row=document(room);room_type=collection('room_types').find_one({'_id':room.get('typeId')});room_row['typeId']=document(room_type) if room_type else None;row['roomId']=room_row
    emp=collection('users').find_one({'_id':b.get('empId')}) if b.get('empId') else None
    row['empId']={'id':str(emp['_id']),'empName':emp.get('name')} if emp else None
    return row

def expand_service_request(row):
    result=document(row)
    room=collection('rooms').find_one({'_id':row.get('roomId')}) if row.get('roomId') else None
    result['roomNumber']=room.get('roomNumber') if room else '—'
    guest=collection('guests').find_one({'_id':row.get('guestId')}) if row.get('guestId') else None
    result['guestName']=f"{guest.get('firstName','')} {guest.get('lastName','')}".strip() if guest else ''
    assigned=collection('users').find_one({'_id':row.get('assignedTo')}) if row.get('assignedTo') else None
    result['assignedToName']=assigned.get('name') if assigned else None
    return result

def parse_oid_or_response(value):
    try: return oid(value)
    except ValidationError: return None

@api_view(['GET','POST','PATCH','DELETE'])
def guest_list(request, record_id=None):
    if request.method=='GET':
        if request.user.role=='guest':
            user=collection('users').find_one({'_id':ObjectId(request.user.id)});row=collection('guests').find_one({'_id':user.get('guestId')}) if user else None
            if not row:return Response({'message':'Guest profile not found.'},status=404)
            safe=document(row);safe={k:safe.get(k) for k in ['id','firstName','lastName','email','phone','address','registeredOn']};return Response([safe])
        if role_denied(request,{'staff','manager'}):return Response({'message':'Staff access required.'},status=403)
        query={};search=request.query_params.get('search')
        if search: query={'$or':[{'firstName':{'$regex':search,'$options':'i'}},{'lastName':{'$regex':search,'$options':'i'}},{'email':{'$regex':search,'$options':'i'}},{'phone':{'$regex':search,'$options':'i'}}]}
        rows=list(collection('guests').find(query).sort('registeredOn',DESCENDING))
        return paged(request,rows)
    if role_denied(request,{'manager'}):return Response({'message':'Manager access required.'},status=403)
    if request.method=='POST':
        values={k:request.data.get(k) for k in ['firstName','lastName','email','phone','address','idProofType','idProofNo']}
        if not values.get('firstName') or not values.get('email') or not values.get('phone'):return Response({'message':'Name, email and phone are required.'},status=400)
        if collection('guests').find_one({'$or':[{'email':values['email'].lower()},{'phone':values['phone']}] }):return Response({'message':'Guest email or phone already exists.'},status=409)
        values.update({'email':values['email'].lower(),'registeredOn':datetime.now(timezone.utc)})
        values=protect_guest_fields(values)
        values['_id']=collection('guests').insert_one(values).inserted_id;audit(request.user,'guest.created','guest',values['_id'])
        return Response(document(values),status=201)
    target=parse_oid_or_response(record_id)
    if target is None:return Response({'message':'Invalid guest id.'},status=400)
    existing=collection('guests').find_one({'_id':target})
    if not existing:return Response({'message':'Guest not found.'},status=404)
    if request.method=='DELETE':
        if collection('bookings').find_one({'guestId':target}):return Response({'message':'Guest has booking history and cannot be deleted.'},status=409)
        collection('guests').delete_one({'_id':target});audit(request.user,'guest.deleted','guest',target);return Response(status=204)
    updates={k:v for k,v in request.data.items() if k in {'firstName','lastName','email','phone','address','idProofType','idProofNo'}}
    updates=protect_guest_fields(updates)
    collection('guests').update_one({'_id':target},{'$set':updates});audit(request.user,'guest.updated','guest',target,{'fields':list(updates)})
    return Response(document(collection('guests').find_one({'_id':target})))

@api_view(['GET','POST','PATCH','DELETE'])
def room_types(request, record_id=None):
    if request.method=='GET':
        if record_id:
            target=parse_oid_or_response(record_id);row=collection('room_types').find_one({'_id':target}) if target else None
            return Response(document(row)) if row else Response({'message':'Room type not found.'},status=404)
        return paged(request,list(collection('room_types').find().sort('typeName',ASCENDING)))
    if role_denied(request,{'manager'}):return Response({'message':'Manager access required.'},status=403)
    if request.method=='POST':
        serializer=RoomTypeSerializer(data=request.data);serializer.is_valid(raise_exception=True);vals=serializer.validated_data
        vals.setdefault('description','');vals.setdefault('amenities',[])
        vals['_id']=collection('room_types').insert_one(vals).inserted_id;audit(request.user,'room_type.created','room_type',vals['_id']);return Response(document(vals),status=201)
    target=parse_oid_or_response(record_id)
    if not target:return Response({'message':'Room type id is required.'},status=400)
    if request.method=='DELETE':
        if collection('rooms').find_one({'typeId':target}):return Response({'message':'Room type is assigned to rooms and cannot be deleted.'},status=409)
        collection('room_types').delete_one({'_id':target});audit(request.user,'room_type.deleted','room_type',target);return Response(status=204)
    if not collection('room_types').find_one({'_id':target}):return Response({'message':'Room type not found.'},status=404)
    serializer=RoomTypeSerializer(data=request.data,partial=True);serializer.is_valid(raise_exception=True);updates=serializer.validated_data
    collection('room_types').update_one({'_id':target},{'$set':updates});audit(request.user,'room_type.updated','room_type',target,{'fields':list(updates)});return Response(document(collection('room_types').find_one({'_id':target})))

@api_view(['GET','POST','PATCH','DELETE'])
def rooms(request, record_id=None):
    if request.method=='GET':
        query={}
        requested_type=parse_oid_or_response(request.query_params['typeId']) if request.query_params.get('typeId') else None
        if request.query_params.get('typeId') and requested_type is None:return Response({'message':'Invalid room type id.'},status=400)
        if requested_type:query['typeId']=requested_type
        if request.query_params.get('status'):query['status']=request.query_params['status']
        filtered_type_ids=None
        if request.query_params.get('minPrice') or request.query_params.get('maxPrice'):
            try:
                type_query={}
                if request.query_params.get('minPrice'):type_query['basePrice']={'$gte':float(request.query_params['minPrice'])}
                if request.query_params.get('maxPrice'):type_query.setdefault('basePrice',{}).update({'$lte':float(request.query_params['maxPrice'])})
                filtered_type_ids=set(collection('room_types').distinct('_id',type_query))
            except ValueError:return Response({'message':'Price filters must be numeric.'},status=400)
        if request.query_params.get('guests'):
            try: capable=set(collection('room_types').distinct('_id',{'maxOccupancy':{'$gte':int(request.query_params['guests'])}}))
            except ValueError:return Response({'message':'Guest count must be a whole number.'},status=400)
            filtered_type_ids=capable if filtered_type_ids is None else filtered_type_ids & capable
        if filtered_type_ids is not None:
            if requested_type:filtered_type_ids=filtered_type_ids & {requested_type}
            query['typeId']={'$in':list(filtered_type_ids)}
        if request.query_params.get('amenities'):query['amenities']={'$all':[x.strip() for x in request.query_params['amenities'].split(',') if x.strip()]}
        start=request.query_params.get('checkInDate');end=request.query_params.get('checkOutDate')
        if bool(start)!=bool(end):return Response({'message':'Provide both check-in and check-out dates.'},status=400)
        if start and end:
            try:
                d1=datetime.fromisoformat(start).replace(tzinfo=timezone.utc);d2=datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
                if d2<=d1:return Response({'message':'Check-out must be after check-in.'},status=400)
                busy=collection('bookings').distinct('roomId',{'bookingStatus':{'$in':['Confirmed','Checked-In']},'checkInDate':{'$lt':d2},'checkOutDate':{'$gt':d1}});query['_id']={'$nin':busy};query['status']={'$nin':['Maintenance','Out of Service']}
            except ValueError:return Response({'message':'Use ISO date values for room availability.'},status=400)
        rows=list(collection('rooms').find(query).sort('roomNumber',ASCENDING));result=[]
        for row in rows:
            x=document(row);rt=collection('room_types').find_one({'_id':row.get('typeId')});x['typeId']=document(rt) if rt else None
            if request.user.role=='guest':x.pop('statusHistory',None)
            result.append(x)
        return paged(request,result)
    if request.method=='POST' and role_denied(request,{'manager'}):return Response({'message':'Manager access required.'},status=403)
    if request.method in {'PATCH','DELETE'} and role_denied(request,{'staff','manager'}):return Response({'message':'Staff access required.'},status=403)
    if request.method=='POST':
        serializer=RoomSerializer(data=request.data);serializer.is_valid(raise_exception=True);vals=serializer.validated_data;vals['typeId']=oid(vals['typeId']);vals.setdefault('status','Available')
        if not collection('room_types').find_one({'_id':vals['typeId']}):return Response({'message':'Room type not found.'},status=400)
        vals['_id']=collection('rooms').insert_one(vals).inserted_id;audit(request.user,'room.created','room',vals['_id']);return Response(document(vals),status=201)
    target=parse_oid_or_response(record_id)
    if not target:return Response({'message':'Room id is required.'},status=400)
    if request.method=='DELETE':
        if request.user.role!='manager':return Response({'message':'Manager access required.'},status=403)
        if collection('bookings').find_one({'roomId':target,'bookingStatus':{'$in':['Confirmed','Checked-In']}}):return Response({'message':'Room has an active booking and cannot be deleted.'},status=409)
        if not collection('rooms').find_one({'_id':target}):return Response({'message':'Room not found.'},status=404)
        collection('rooms').delete_one({'_id':target});audit(request.user,'room.deleted','room',target);return Response(status=204)
    updates={k:v for k,v in request.data.items() if k in {'roomNumber','floorNo','typeId','status','capacity','amenities','images'}}
    if request.user.role=='staff' and set(updates)-{'status'}:return Response({'message':'Staff may only change room readiness status.'},status=403)
    if request.user.role=='staff' and updates.get('status') not in {'Cleaning','Inspected','Available'}:return Response({'message':'Staff may set rooms to Cleaning, Inspected, or Available.'},status=403)
    if not collection('rooms').find_one({'_id':target}):return Response({'message':'Room not found.'},status=404)
    if 'typeId' in updates:updates['typeId']=oid(updates['typeId'])
    if updates.get('status') not in {None,'Available','Occupied','Maintenance','Cleaning','Inspected','Out of Service'}:return Response({'message':'Unknown room status.'},status=400)
    if updates.get('status') and updates['status']!='Occupied' and collection('bookings').find_one({'roomId':target,'bookingStatus':'Checked-In'}):return Response({'message':'A checked-in guest is occupying this room.'},status=409)
    if updates.get('status')=='Available' and collection('bookings').find_one({'roomId':target,'bookingStatus':'Checked-In'}):return Response({'message':'Room is currently occupied.'},status=409)
    update_doc={'$set':updates}
    if 'status' in updates:update_doc['$push']={'statusHistory':{'status':updates['status'],'actorId':ObjectId(request.user.id),'actorName':request.user.name,'at':datetime.now(timezone.utc)}}
    collection('rooms').update_one({'_id':target},update_doc);audit(request.user,'room.updated','room',target,{'fields':list(updates)});return Response(document(collection('rooms').find_one({'_id':target})))

@api_view(['GET'])
def employees(request):
    if role_denied(request,{'staff','manager'}):return Response({'message':'Staff access required.'},status=403)
    rows=collection('users').find({'role':{'$in':['staff','manager']},'active':True}).sort('name',ASCENDING)
    return paged(request,[{'id':str(x['_id']),'empName':x.get('name'),'email':x['email'],'designation':x.get('designation','Receptionist'),'role':x['role']} for x in rows])

@api_view(['GET','POST','PATCH','DELETE'])
def services(request,record_id=None):
    if request.method=='GET':
        if record_id:
            target=parse_oid_or_response(record_id);row=collection('services').find_one({'_id':target,'active':{'$ne':False}}) if target else None
            return Response(document(row)) if row else Response({'message':'Service not found.'},status=404)
        return paged(request,list(collection('services').find({'active':{'$ne':False}}).sort('serviceName',ASCENDING)))
    if role_denied(request,{'manager'}):return Response({'message':'Manager access required.'},status=403)
    if request.method=='DELETE':
        target=parse_oid_or_response(record_id)
        if not target:return Response({'message':'Service id is required.'},status=400)
        collection('services').update_one({'_id':target},{'$set':{'active':False}});audit(request.user,'service.deactivated','service',target);return Response(status=204)
    if request.method=='PATCH':
        target=parse_oid_or_response(record_id)
        serializer=ServiceCatalogSerializer(data=request.data,partial=True);serializer.is_valid(raise_exception=True);updates=serializer.validated_data
        if not updates:return Response({'message':'No service changes provided.'},status=400)
        if not target or not collection('services').find_one({'_id':target}):return Response({'message':'Service not found.'},status=404)
        collection('services').update_one({'_id':target},{'$set':updates});audit(request.user,'service.updated','service',target,{'fields':list(updates)});return Response(document(collection('services').find_one({'_id':target})))
    serializer=ServiceCatalogSerializer(data={**request.data,'category':request.data.get('category','Other')});serializer.is_valid(raise_exception=True);values=serializer.validated_data
    row={**values,'description':values.get('description',''),'active':True};row['_id']=collection('services').insert_one(row).inserted_id;audit(request.user,'service.created','service',row['_id']);return Response(document(row),status=201)

@api_view(['GET','POST','DELETE'])
def bookings(request, record_id=None):
    if request.method=='GET':
        if record_id:
            target=parse_oid_or_response(record_id);row=collection('bookings').find_one({'_id':target}) if target else None
            if not row:return Response({'message':'Booking not found.'},status=404)
            if request.user.role=='guest' and row.get('guestId')!=collection('users').find_one({'_id':ObjectId(request.user.id)}).get('guestId'):return Response({'message':'You cannot view this booking.'},status=403)
            return Response(expand_booking(row))
        query={}
        user=collection('users').find_one({'_id':ObjectId(request.user.id)})
        if request.user.role=='guest':query['guestId']=user.get('guestId')
        elif request.query_params.get('status'):query['bookingStatus']=request.query_params['status']
        rows=list(collection('bookings').find(query).sort('bookingDate',DESCENDING));result=[expand_booking(x) for x in rows]
        if request.path.endswith('/dues'):
            for row in result:
                b=collection('bookings').find_one({'_id':ObjectId(row['id'])});paid=sum(p['amount'] for p in collection('payments').find({'bookingId':b['_id'],'paymentStatus':'Paid'}));row['paidAmount']=paid;row['dueAmount']=max(0,b.get('totalAmount',0)-paid)
            return Response(result)
        return paged(request,result)
    if request.method=='POST':
        if request.user.role not in {'guest','staff','manager'}:return Response({'message':'Account cannot create bookings.'},status=403)
        serializer=BookingSerializer(data=request.data);serializer.is_valid(raise_exception=True);values=serializer.validated_data
        if request.user.role=='guest':
            user=collection('users').find_one({'_id':ObjectId(request.user.id)});values['guestId']=str(user.get('guestId'))
        if not values.get('empId'):
            employee=collection('users').find_one({'role':'staff','active':True});values['empId']=str(employee['_id']) if employee else ''
        try:created=create_booking(values,request.user)
        except (ValueError,KeyError) as e:return Response({'message':str(e)},status=400)
        audit(request.user,'booking.created','booking',created['_id']);return Response(expand_booking(created),status=201)
    if request.method=='DELETE':
        if role_denied(request,{'manager'}):return Response({'message':'Manager access required.'},status=403)
        target=parse_oid_or_response(record_id)
        if not target:return Response({'message':'Invalid booking id.'},status=400)
        if collection('payments').find_one({'bookingId':target}):return Response({'message':'A booking with payment history cannot be deleted.'},status=409)
        collection('bookings').delete_one({'_id':target});collection('booking_services').delete_many({'bookingId':target});audit(request.user,'booking.deleted','booking',target);return Response(status=204)

@api_view(['PATCH'])
def booking_status(request,record_id):
    target=parse_oid_or_response(record_id);booking=collection('bookings').find_one({'_id':target}) if target else None
    if not booking:return Response({'message':'Booking not found.'},status=404)
    new=request.data.get('bookingStatus')
    if new=='Cancelled':
        if request.user.role=='guest':
            user=collection('users').find_one({'_id':ObjectId(request.user.id)})
            if booking.get('guestId')!=user.get('guestId') or booking['bookingStatus']!='Confirmed':return Response({'message':'Only your confirmed bookings can be cancelled.'},status=403)
        elif role_denied(request,{'staff','manager'}):return Response({'message':'Staff access required.'},status=403)
    elif new in {'Checked-In','Checked-Out'} and role_denied(request,{'staff','manager'}):return Response({'message':'Staff access required.'},status=403)
    if not booking_transition_allowed(booking['bookingStatus'],new):return Response({'message':f"Cannot change {booking['bookingStatus']} to {new}."},status=400)
    updates={'bookingStatus':new,'updatedAt':datetime.now(timezone.utc)}
    if new=='Checked-Out':
        updates['totalAmount']=bill_for(booking)
        updates['priceBreakdown.total']=updates['totalAmount']
    if new=='Cancelled':updates.update({'totalAmount':0})
    collection('bookings').update_one({'_id':target},{'$set':updates})
    room_status='Occupied' if new=='Checked-In' else 'Cleaning' if new=='Checked-Out' else 'Available' if new=='Cancelled' else None
    if room_status:
        at=datetime.now(timezone.utc)
        collection('rooms').update_one({'_id':booking['roomId']},{'$set':{'status':room_status,'updatedAt':at},'$push':{'statusHistory':{'status':room_status,'actorId':ObjectId(request.user.id),'actorName':request.user.name,'at':at}}})
    audit(request.user,f'booking.{new.lower()}','booking',target);return Response(expand_booking(collection('bookings').find_one({'_id':target})))

@api_view(['GET','POST','PATCH','DELETE'])
def booking_services(request,record_id):
    target=parse_oid_or_response(record_id);booking=collection('bookings').find_one({'_id':target}) if target else None
    if not booking:return Response({'message':'Booking not found.'},status=404)
    if request.method=='GET':return Response(documents(collection('booking_services').find({'bookingId':target})))
    if role_denied(request,{'staff','manager'}):return Response({'message':'Staff access required.'},status=403)
    if booking['bookingStatus']!='Checked-In':return Response({'message':'Services may only be charged during a checked-in stay.'},status=400)
    service_id=parse_oid_or_response(request.data.get('serviceId',''));service=collection('services').find_one({'_id':service_id}) if service_id else None
    quantity=int(request.data.get('quantity',1))
    if not service or quantity<1:return Response({'message':'Choose a valid service and quantity.'},status=400)
    line={'bookingId':target,'serviceId':service_id,'serviceName':service['serviceName'],'quantity':quantity,'priceEach':service['price'],'serviceDate':datetime.now(timezone.utc)};line['_id']=collection('booking_services').insert_one(line).inserted_id
    add=service['price']*quantity;collection('bookings').update_one({'_id':target},{'$inc':{'totalAmount':add,'priceBreakdown.total':add}});audit(request.user,'booking.service_added','booking',target,{'service':service['serviceName'],'quantity':quantity});return Response(document(line),status=201)

@api_view(['GET'])
def booking_bill(request,record_id):
    target=parse_oid_or_response(record_id);booking=collection('bookings').find_one({'_id':target}) if target else None
    if not booking:return Response({'message':'Booking not found.'},status=404)
    if request.user.role=='guest':
        user=collection('users').find_one({'_id':ObjectId(request.user.id)})
        if user.get('guestId')!=booking.get('guestId'):return Response({'message':'You cannot view this bill.'},status=403)
    return Response({'total':bill_for(booking),'priceBreakdown':booking.get('priceBreakdown',{})})

@api_view(['GET','POST'])
def payments(request):
    if request.method=='GET':
        query={}
        if request.user.role=='guest':
            user=collection('users').find_one({'_id':ObjectId(request.user.id)});ids=collection('bookings').distinct('_id',{'guestId':user.get('guestId')});query['bookingId']={'$in':ids}
        elif request.user.role not in {'staff','manager'}:return Response({'message':'Staff access required.'},status=403)
        rows=list(collection('payments').find(query).sort('paymentDate',DESCENDING))
        if request.user.role=='guest':
            for row in rows:row.pop('recordedBy',None)
        return paged(request,rows)
    if role_denied(request,{'staff','manager'}):return Response({'message':'Staff access required.'},status=403)
    serializer=PaymentSerializer(data=request.data);serializer.is_valid(raise_exception=True);v=serializer.validated_data;booking_id=oid(v['bookingId']);booking=collection('bookings').find_one({'_id':booking_id})
    if not booking or booking['bookingStatus']=='Cancelled':return Response({'message':'Active booking not found.'},status=404)
    paid=sum(p['amount'] for p in collection('payments').find({'bookingId':booking_id,'paymentStatus':'Paid'}));amount=float(v['amount']);due=booking.get('totalAmount',0)-paid
    if amount>due:return Response({'message':f'Payment exceeds the remaining balance of ₹{due:.2f}.'},status=400)
    row={'bookingId':booking_id,'amount':amount,'paymentMethod':v['paymentMethod'],'paymentStatus':'Paid','paymentDate':datetime.now(timezone.utc),'recordedBy':ObjectId(request.user.id)};row['_id']=collection('payments').insert_one(row).inserted_id
    if paid+amount>=booking.get('totalAmount',0):collection('bookings').update_one({'_id':booking_id},{'$set':{'paymentStatus':'Paid'}})
    audit(request.user,'payment.recorded','payment',row['_id'],{'amount':amount});return Response(document(row),status=201)

@api_view(['GET','POST','PATCH','DELETE'])
def service_requests(request,record_id=None):
    if request.method=='GET':
        query={}
        if request.user.role=='guest':query['guestId']=ObjectId(collection('users').find_one({'_id':ObjectId(request.user.id)}).get('guestId'))
        elif request.user.role=='staff':query['$or']=[{'assignedTo':ObjectId(request.user.id)},{'assignedTo':None}]
        elif request.user.role!='manager':return Response({'message':'Access denied.'},status=403)
        for key in ['status','category','priority','roomId']:
            if request.query_params.get(key):query[key]=ObjectId(request.query_params[key]) if key=='roomId' else request.query_params[key]
        rows=list(collection('service_requests').find(query).sort('createdAt',DESCENDING))
        if request.user.role=='guest':
            safe=[]
            for row in rows:
                item=expand_service_request(row);item.pop('assignedTo',None);item.pop('assignedToName',None);item['history']=[{'action':h.get('action'),'at':h.get('at')} for h in row.get('history',[])];safe.append(item)
            return paged(request,safe)
        return paged(request,[expand_service_request(x) for x in rows])
    if request.method=='POST':
        if request.user.role not in {'guest','staff','manager'}:return Response({'message':'Access denied.'},status=403)
        serializer=ServiceRequestSerializer(data=request.data);serializer.is_valid(raise_exception=True);v=serializer.validated_data;room_id=oid(v['roomId']);room=collection('rooms').find_one({'_id':room_id})
        if not room:return Response({'message':'Room not found.'},status=404)
        booking_id=oid(v['bookingId']) if v.get('bookingId') else None
        if request.user.role=='guest':
            user=collection('users').find_one({'_id':ObjectId(request.user.id)})
            if not booking_id or not collection('bookings').find_one({'_id':booking_id,'guestId':user.get('guestId'),'roomId':room_id,'bookingStatus':'Checked-In'}):return Response({'message':'Service requests require your active checked-in booking.'},status=403)
            guest_id=user.get('guestId')
        else:guest_id=collection('bookings').find_one({'_id':booking_id}).get('guestId') if booking_id and collection('bookings').find_one({'_id':booking_id}) else None
        row={'guestId':guest_id,'bookingId':booking_id,'roomId':room_id,'category':v['category'],'description':v['description'],'priority':v['priority'],'status':'New','assignedTo':ObjectId(request.user.id) if request.user.role=='staff' else None,'createdAt':datetime.now(timezone.utc),'history':[{'actorId':ObjectId(request.user.id),'action':'created','at':datetime.now(timezone.utc)}]};row['_id']=collection('service_requests').insert_one(row).inserted_id;audit(request.user,'service_request.created','service_request',row['_id']);return Response(document(row),status=201)
    if request.user.role not in {'staff','manager'}:return Response({'message':'Staff access required.'},status=403)
    target=parse_oid_or_response(record_id)
    if not target:return Response({'message':'Invalid request id.'},status=400)
    existing=collection('service_requests').find_one({'_id':target})
    if not existing:return Response({'message':'Request not found.'},status=404)
    if request.user.role=='staff' and existing.get('assignedTo') not in [None,ObjectId(request.user.id)]:return Response({'message':'This task is assigned to another staff member.'},status=403)
    if request.method=='DELETE':
        if request.user.role!='manager':return Response({'message':'Manager access required.'},status=403)
        collection('service_requests').delete_one({'_id':target});audit(request.user,'service_request.deleted','service_request',target);return Response(status=204)
    if request.method=='PATCH':
        if request.user.role=='manager' and 'assignedTo' in request.data:
            assigned=parse_oid_or_response(request.data['assignedTo']) if request.data['assignedTo'] else None
            staff=collection('users').find_one({'_id':assigned,'role':'staff','active':True}) if assigned else None
            if assigned and not staff:return Response({'message':'Choose an active staff account.'},status=400)
            action='assigned' if assigned else 'unassigned';history={'actorId':ObjectId(request.user.id),'actorName':request.user.name,'action':action,'note':staff.get('name','') if staff else '','at':datetime.now(timezone.utc)}
            collection('service_requests').update_one({'_id':target},{'$set':{'assignedTo':assigned,'updatedAt':history['at']},'$push':{'history':history}});audit(request.user,f'service_request.{action}','service_request',target,{'assignedTo':str(assigned) if assigned else None});return Response(document(collection('service_requests').find_one({'_id':target})))
        serializer=StatusSerializer(data=request.data);serializer.is_valid(raise_exception=True);v=serializer.validated_data
        if not service_request_transition_allowed(existing.get('status','New'),v['status']):return Response({'message':f"Cannot change {existing.get('status')} to {v['status']}."},status=400)
        entry={'actorId':ObjectId(request.user.id),'actorName':request.user.name,'action':v['status'],'note':v.get('note',''),'at':datetime.now(timezone.utc)}
        sets={'status':v['status'],'updatedAt':entry['at']}
        if v['status']=='Completed':sets['completedAt']=entry['at']
        update={'$set':sets,'$push':{'history':entry}}
        if request.user.role=='staff' and existing.get('assignedTo') is None:update['$set']['assignedTo']=ObjectId(request.user.id)
        collection('service_requests').update_one({'_id':target},update);audit(request.user,'service_request.status_changed','service_request',target,{'status':v['status']})
        return Response(document(collection('service_requests').find_one({'_id':target})))
    return Response(document(existing))

@api_view(['GET'])
def dashboard(request):
    if role_denied(request,{'staff','manager'}):return Response({'message':'Staff access required.'},status=403)
    rooms=collection('rooms');bookings=collection('bookings');service_requests_col=collection('service_requests')
    total_rooms=rooms.count_documents({});occupied=rooms.count_documents({'status':'Occupied'});active=bookings.count_documents({'bookingStatus':{'$in':['Confirmed','Checked-In']}})
    revenue=list(collection('payments').aggregate([{'$match':{'paymentStatus':'Paid'}},{'$group':{'_id':None,'total':{'$sum':'$amount'}}}]))
    statuses=[{'id':s,'count':rooms.count_documents({'status':s})} for s in ['Occupied','Available','Maintenance','Cleaning','Inspected','Out of Service']]
    open_requests=service_requests_col.count_documents({'status':{'$in':['New','Pending','In Progress']}})
    return Response({'guests':collection('guests').count_documents({}),'rooms':total_rooms,'activeBookings':active,'revenue':revenue[0]['total'] if revenue else 0,'occupancy':round(occupied/total_rooms*100) if total_rooms else 0,'roomStatus':statuses,'unresolvedRequests':open_requests,'checkedIn':bookings.count_documents({'bookingStatus':'Checked-In'})})

@api_view(['GET'])
def reports(request):
    if role_denied(request,{'manager'}):return Response({'message':'Manager access required.'},status=403)
    start=request.query_params.get('from');end=request.query_params.get('to');match={}
    if start or end:
        match['paymentDate']={}
        try:
            if start:match['paymentDate']['$gte']=datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
            if end:match['paymentDate']['$lte']=datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
        except ValueError:return Response({'message':'Report dates must use YYYY-MM-DD.'},status=400)
    match['paymentStatus']='Paid'
    revenue=[{'id':x['_id'],'revenue':x['revenue']} for x in collection('payments').aggregate([{'$match':match},{'$group':{'_id':{'$dateToString':{'format':'%Y-%m','date':'$paymentDate'}},'revenue':{'$sum':'$amount'}}},{'$sort':{'_id':1}}])]
    by_status=[{'id':name,'count':collection('bookings').count_documents({'bookingStatus':name})} for name in ['Confirmed','Checked-In','Checked-Out','Cancelled']]
    top=collection('booking_services').aggregate([{'$group':{'_id':'$serviceId','quantity':{'$sum':'$quantity'}}},{'$sort':{'quantity':-1}},{'$limit':5}]);top_services=[]
    for x in top:
        service=collection('services').find_one({'_id':x['_id']});top_services.append({'id':str(x['_id']),'quantity':x['quantity'],'service':document(service)})
    cancelled=collection('bookings').count_documents({'bookingStatus':'Cancelled'})
    report={'byStatus':by_status,'topServices':top_services,'monthlyRevenue':revenue,'guests':collection('guests').count_documents({}),'bookings':collection('bookings').count_documents({}),'cancellations':cancelled,'unresolvedRequests':collection('service_requests').count_documents({'status':{'$in':['New','Pending','In Progress']}})}
    if request.query_params.get('format')=='csv':
        response=HttpResponse(content_type='text/csv');response['Content-Disposition']='attachment; filename="lumen-house-report.csv"';writer=csv.writer(response);writer.writerow(['Monthly revenue']);writer.writerow(['Month','Revenue INR']);writer.writerows([[x['id'],x['revenue']] for x in revenue]);writer.writerow([]);writer.writerow(['Booking status','Count']);writer.writerows([[x['id'],x['count']] for x in by_status]);writer.writerow([]);writer.writerow(['Cancellations',cancelled]);writer.writerow(['Unresolved service requests',report['unresolvedRequests']]);return response
    return Response(report)

@api_view(['GET'])
def staff_dashboard(request):
    if role_denied(request,{'staff','manager'}):return Response({'message':'Staff access required.'},status=403)
    query={'$or':[{'assignedTo':ObjectId(request.user.id)},{'assignedTo':None}]} if request.user.role=='staff' else {}
    rows=list(collection('service_requests').find(query).sort([('priority',DESCENDING),('createdAt',ASCENDING)]).limit(100))
    return Response({'serviceRequests':[expand_service_request(x) for x in rows],'counts':{s:collection('service_requests').count_documents({**query,'status':s}) for s in ['New','Pending','In Progress','Completed']}})

@api_view(['GET'])
def audit_logs(request):
    if role_denied(request,{'manager'}):return Response({'message':'Manager access required.'},status=403)
    return paged(request,list(collection('audit_logs').find().sort('createdAt',DESCENDING)))

@api_view(['GET','POST','PATCH','DELETE'])
def staff_accounts(request,record_id=None):
    if role_denied(request,{'manager'}):return Response({'message':'Manager access required.'},status=403)
    if request.method=='GET':
        rows=list(collection('users').find({'role':'staff'}).sort('name',ASCENDING))
        return paged(request,[{'id':str(x['_id']),'name':x.get('name'),'email':x['email'],'phone':x.get('phone'),'designation':x.get('designation'),'active':x.get('active',True)} for x in rows])
    if request.method=='POST':
        from django.contrib.auth.hashers import make_password
        name=request.data.get('name','').strip();email=request.data.get('email','').lower();password=request.data.get('password','');designation=request.data.get('designation','Receptionist')
        if not name or not email or len(password)<10:return Response({'message':'Name, email, and a password of at least 10 characters are required.'},status=400)
        if collection('users').find_one({'email':email}):return Response({'message':'This email already has an account.'},status=409)
        row={'name':name,'email':email,'phone':request.data.get('phone',''),'passwordHash':make_password(password),'role':'staff','designation':designation,'active':True,'createdAt':datetime.now(timezone.utc)};row['_id']=collection('users').insert_one(row).inserted_id;audit(request.user,'staff.created','user',row['_id']);return Response({'id':str(row['_id']),'name':name,'email':email,'designation':designation,'active':True},status=201)
    target=parse_oid_or_response(record_id);staff=collection('users').find_one({'_id':target,'role':'staff'}) if target else None
    if not staff:return Response({'message':'Staff account not found.'},status=404)
    if request.method=='DELETE':
        collection('users').update_one({'_id':target},{'$set':{'active':False,'deactivatedAt':datetime.now(timezone.utc)}});audit(request.user,'staff.deactivated','user',target);return Response(status=204)
    updates={k:v for k,v in request.data.items() if k in {'name','phone','designation','active'}}
    if not updates:return Response({'message':'No editable staff fields provided.'},status=400)
    collection('users').update_one({'_id':target},{'$set':updates});audit(request.user,'staff.updated','user',target,{'fields':list(updates)});return Response({'id':str(target),**updates})
