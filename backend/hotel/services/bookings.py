from datetime import datetime, time, timezone
from bson import ObjectId
from hotel.db import collection

ACTIVE = ['Confirmed', 'Checked-In']

def as_utc(d, end=False):
    return datetime.combine(d, time.min, tzinfo=timezone.utc)

def create_booking(values, actor):
    guest_id = ObjectId(values['guestId'])
    room_id = ObjectId(values['roomId'])
    room = collection('rooms').find_one({'_id': room_id})
    if not room:
        raise ValueError('Room not found.')
    if room.get('status') in ['Maintenance','Out of Service']:
        raise ValueError('This room is not available for booking.')
    if values['numGuests'] > room.get('capacity', 2):
        raise ValueError(f"Room capacity is {room.get('capacity', 2)} guests.")
    check_in, check_out = as_utc(values['checkInDate']), as_utc(values['checkOutDate'])
    conflict = collection('bookings').find_one({'roomId': room_id, 'bookingStatus': {'$in': ACTIVE}, 'checkInDate': {'$lt': check_out}, 'checkOutDate': {'$gt': check_in}})
    if conflict:
        raise ValueError('Room is already booked for those dates.')
    guest = collection('guests').find_one({'_id': guest_id})
    if not guest:
        raise ValueError('Guest record not found.')
    room_type = collection('room_types').find_one({'_id': room['typeId']})
    nights = (values['checkOutDate'] - values['checkInDate']).days
    rate = room_type['basePrice']
    service_fee = round(rate * nights * 0.05, 2)
    total = round(rate * nights + service_fee, 2)
    assigned = ObjectId(values['empId']) if actor.role != 'guest' and values.get('empId') else ObjectId(actor.id) if actor.role != 'guest' else room.get('defaultEmployeeId')
    booking = {'guestId': guest_id, 'roomId': room_id, 'empId': assigned, 'checkInDate': check_in, 'checkOutDate': check_out, 'numGuests': values['numGuests'], 'bookingStatus': 'Confirmed', 'paymentStatus': 'Pending', 'priceBreakdown': {'nightlyRate': rate, 'nights': nights, 'roomSubtotal': rate*nights, 'taxesAndFees': service_fee, 'discount': 0, 'total': total}, 'totalAmount': total, 'bookingDate': datetime.now(timezone.utc), 'createdBy': ObjectId(actor.id)}
    if booking['empId'] is None:
        employee = collection('users').find_one({'role': 'staff', 'active': True})
        booking['empId'] = employee['_id'] if employee else None
    result = collection('bookings').insert_one(booking)
    booking['_id'] = result.inserted_id
    return booking

def bill_for(booking):
    room_type = collection('room_types').find_one({'_id': collection('rooms').find_one({'_id': booking['roomId']})['typeId']})
    nights = max(1, (booking['checkOutDate'].date() - booking['checkInDate'].date()).days)
    service_total = sum(x['quantity'] * x['priceEach'] for x in collection('booking_services').find({'bookingId': booking['_id']}))
    return round(nights * room_type['basePrice'] + booking.get('priceBreakdown', {}).get('taxesAndFees', 0) + service_total, 2)
