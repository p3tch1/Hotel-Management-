from datetime import datetime, timedelta, timezone
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from bson import ObjectId
from hotel.db import collection, database
from hotel.encryption import protect_guest_fields

NAMES=['Anika Sharma','Vikram Rao','Sana Kapoor','Ishaan Nair','Riya Menon','Aarav Das','Maya Iyer','Karan Patel','Leela Sen','Kabir Bose']
TYPES=['Classic','Deluxe','Executive Suite','Garden Suite','Family Room','Twin Classic','Premium Deluxe','Penthouse','Accessible Deluxe','Courtyard Room']
SERVICES=['Breakfast for Two','Airport Transfer','Laundry Bundle','Spa Treatment','In-Room Dining','City Tour','Late Checkout','Valet Parking','Afternoon Tea','Fitness Session']

class Command(BaseCommand):
    help='Replace the demo records and load 30 documents in each core collection.'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Confirm that all current demo collections may be cleared.')

    def handle(self, *args, **options):
        if not options['yes']:
            raise SystemExit('This command clears project collections. Re-run with --yes to confirm.')
        db=database()
        names=['users','guests','room_types','rooms','employees','services','bookings','booking_services','payments','service_requests','audit_logs','revoked_tokens','auth_events']
        for name in names: db[name].delete_many({})
        db.users.create_index('email',unique=True);db.guests.create_index('email',unique=True);db.guests.create_index('phone',unique=True);db.rooms.create_index('roomNumber',unique=True);db.room_types.create_index('typeName',unique=True);db.services.create_index('serviceName',unique=True)
        db.revoked_tokens.create_index('expiresAt',expireAfterSeconds=0)
        now=datetime.now(timezone.utc)
        types=[]
        for i in range(30):
            row={'typeName':TYPES[i] if i<10 else f'Signature Room {i+1}','description':'Thoughtfully appointed room for a comfortable city stay.','basePrice':3200+(i%10)*1250,'maxOccupancy':[2,3,4,4,5,2,3,6,2,2][i%10],'amenities':['Wi-Fi','Air conditioning','Room service']}
            row['_id']=db.room_types.insert_one(row).inserted_id;types.append(row)
        rooms=[]
        for i,rt in enumerate(types):
            row={'roomNumber':f'{i//10+1}{i%10+1:02d}','floorNo':i//10+1,'typeId':rt['_id'],'capacity':rt['maxOccupancy'],'amenities':rt['amenities'],'images':['https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=900&q=80'],'status':'Occupied' if i<6 else 'Out of Service' if i==29 else 'Available'}
            row['_id']=db.rooms.insert_one(row).inserted_id;rooms.append(row)
        staff=[]
        for i in range(4):
            user={'name':['Ava Kapoor','Rohan Das','Meera Iyer','Kabir Shah'][i],'email':f'staff{i+1}@lumenhotel.example','phone':f'900000000{i+1}','passwordHash':make_password('StaffDemo123!'),'role':'staff','designation':['Receptionist','Housekeeping','Chef','Security'][i],'active':True,'createdAt':now}
            user['_id']=db.users.insert_one(user).inserted_id;staff.append(user)
        manager={'name':'Alex Morgan','email':'manager@lumenhotel.example','phone':'9000000099','passwordHash':make_password('ManagerDemo123!'),'role':'manager','designation':'Property Manager','active':True,'createdAt':now}
        manager['_id']=db.users.insert_one(manager).inserted_id
        service_rows=[]
        categories=['Dining','Transport','Laundry','Wellness','Dining','Transport','Other','Other','Dining','Wellness']
        for i in range(30):
            row={'serviceName':SERVICES[i] if i<10 else f'Guest Service {i+1}','category':categories[i%10],'price':500+(i%10)*350,'description':'Available to hotel guests during their stay.','active':True}
            row['_id']=db.services.insert_one(row).inserted_id;service_rows.append(row)
        guests=[];guest_users=[]
        for i in range(30):
            first,last=NAMES[i%10].split(' ');guest={'firstName':first,'lastName':last,'email':f'guest{i+1}@example.com','phone':f'98800000{i:02d}','address':['New Delhi, India','Mumbai, India','Chennai, India','Bengaluru, India'][i%4],'idProofType':['Aadhaar','Passport','Driving License','Voter ID'][i%4],'idProofNo':f'ID-{i+1:05d}','registeredOn':now}
            stored_guest=protect_guest_fields(guest)
            guest['_id']=db.guests.insert_one(stored_guest).inserted_id;guests.append(guest)
            user={'name':f'{first} {last}','email':guest['email'],'phone':guest['phone'],'passwordHash':make_password('GuestDemo123!'),'role':'guest','active':True,'guestId':guest['_id'],'createdAt':now}
            user['_id']=db.users.insert_one(user).inserted_id;guest_users.append(user)
        bookings=[]
        for i,guest in enumerate(guests):
            checked=i<6;start=now+timedelta(days=-1 if checked else i-4);nights=2+i%3;end=start+timedelta(days=nights);rt=types[i];service=service_rows[i];qty=1+i%2;tax=round(rt['basePrice']*nights*.05,2);subtotal=rt['basePrice']*nights;total=round(subtotal+tax+service['price']*qty,2)
            row={'guestId':guest['_id'],'roomId':rooms[i]['_id'],'empId':staff[i%len(staff)]['_id'],'checkInDate':start,'checkOutDate':end,'numGuests':min(2,rt['maxOccupancy']),'bookingStatus':'Checked-In' if checked else 'Confirmed','paymentStatus':'Pending','bookingDate':now-timedelta(days=i),'priceBreakdown':{'nightlyRate':rt['basePrice'],'nights':nights,'roomSubtotal':subtotal,'taxesAndFees':tax,'discount':0,'total':total},'totalAmount':total,'createdBy':staff[i%len(staff)]['_id']}
            row['_id']=db.bookings.insert_one(row).inserted_id;bookings.append(row)
            db.booking_services.insert_one({'bookingId':row['_id'],'serviceId':service['_id'],'serviceName':service['serviceName'],'quantity':qty,'priceEach':service['price'],'serviceDate':now})
            amount=round(total*(.5 if i%3==0 else .2),2);payment={'bookingId':row['_id'],'amount':amount,'paymentMethod':['UPI','Card','Cash','Net Banking'][i%4],'paymentStatus':'Paid','paymentDate':now-timedelta(days=i),'recordedBy':staff[i%len(staff)]['_id']};db.payments.insert_one(payment)
            if i<12:
                req={'guestId':guest['_id'],'bookingId':row['_id'],'roomId':rooms[i]['_id'],'category':['Housekeeping','Extra Towels','Room Service','Maintenance'][i%4],'description':'Demo service request for the guest stay.','priority':['Normal','High','Low'][i%3],'status':['New','Pending','In Progress','Completed'][i%4],'assignedTo':staff[i%len(staff)]['_id'],'createdAt':now-timedelta(hours=i),'history':[]};db.service_requests.insert_one(req)
        self.stdout.write(self.style.SUCCESS('Demo data seeded: 30 guests, 30 rooms, 30 room types, 30 services, 30 bookings, 30 service lines, 30 payments, plus role accounts and service requests.'))
        self.stdout.write('Demo sign-ins: manager@lumenhotel.example / ManagerDemo123! | staff1@lumenhotel.example / StaffDemo123! | guest1@example.com / GuestDemo123!')
