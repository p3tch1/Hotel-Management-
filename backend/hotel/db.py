from functools import lru_cache
from django.conf import settings
from pymongo import MongoClient

@lru_cache(maxsize=1)
def client():
    return MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)

def database():
    return _configured_database()

@lru_cache(maxsize=1)
def _configured_database():
    db=client()[settings.MONGODB_DATABASE]
    db.users.create_index('email',unique=True)
    db.guests.create_index('email',unique=True)
    db.guests.create_index('phone',unique=True)
    db.rooms.create_index('roomNumber',unique=True)
    db.room_types.create_index('typeName',unique=True)
    db.services.create_index('serviceName',unique=True)
    db.bookings.create_index([('roomId',1),('bookingStatus',1),('checkInDate',1),('checkOutDate',1)])
    db.service_requests.create_index([('status',1),('assignedTo',1),('createdAt',-1)])
    db.payments.create_index([('bookingId',1),('paymentStatus',1)])
    db.revoked_tokens.create_index('expiresAt',expireAfterSeconds=0)
    return db

def collection(name):
    return database()[name]
