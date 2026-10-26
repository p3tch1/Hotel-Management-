from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from bson import ObjectId
from django.test import SimpleTestCase
from hotel.permissions import IsGuest, IsStaff, IsManager
from hotel.serializers import BookingSerializer, RegisterSerializer, StatusSerializer
from hotel.services.bookings import create_booking
from hotel.services.workflows import booking_transition_allowed, service_request_transition_allowed

class SerializerRulesTests(SimpleTestCase):
    def test_booking_rejects_checkout_before_checkin(self):
        data={'guestId':str(ObjectId()),'roomId':str(ObjectId()),'empId':'','checkInDate':(date.today()+timedelta(days=2)).isoformat(),'checkOutDate':(date.today()+timedelta(days=1)).isoformat(),'numGuests':1}
        serializer=BookingSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('checkOutDate',serializer.errors)

    def test_registration_requires_long_password(self):
        serializer=RegisterSerializer(data={'firstName':'Test','email':'t@example.com','phone':'123','password':'short'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('password',serializer.errors)

    def test_service_request_status_is_allow_listed(self):
        serializer=StatusSerializer(data={'status':'Made Up'})
        self.assertFalse(serializer.is_valid())

class RolePermissionTests(SimpleTestCase):
    def principal(self,role):return SimpleNamespace(role=role,is_authenticated=True)
    def test_guest_cannot_pass_staff_or_manager_permissions(self):
        request=SimpleNamespace(user=self.principal('guest'))
        self.assertFalse(IsStaff().has_permission(request,None))
        self.assertFalse(IsManager().has_permission(request,None))
        self.assertTrue(IsGuest().has_permission(request,None))

    def test_manager_has_manager_permission(self):
        self.assertTrue(IsManager().has_permission(SimpleNamespace(user=self.principal('manager')),None))

class BookingBusinessRuleTests(SimpleTestCase):
    def test_confirmed_booking_can_cancel_but_checked_in_cannot(self):
        self.assertTrue(booking_transition_allowed('Confirmed','Cancelled'))
        self.assertFalse(booking_transition_allowed('Checked-In','Cancelled'))

    def test_service_request_workflow_requires_progress_before_completion(self):
        self.assertTrue(service_request_transition_allowed('New','In Progress'))
        self.assertTrue(service_request_transition_allowed('In Progress','Completed'))
        self.assertFalse(service_request_transition_allowed('New','Completed'))

    def test_overlapping_booking_is_rejected(self):
        guest_id,room_id=ObjectId(),ObjectId();room_type_id=ObjectId()
        collections={'rooms':Mock(),'bookings':Mock(),'guests':Mock(),'room_types':Mock(),'users':Mock()}
        collections['rooms'].find_one.return_value={'_id':room_id,'typeId':room_type_id,'capacity':2,'status':'Available'}
        collections['bookings'].find_one.return_value={'_id':ObjectId()}
        with patch('hotel.services.bookings.collection',side_effect=lambda name:collections[name]):
            with self.assertRaisesRegex(ValueError,'already booked'):
                create_booking({'guestId':str(guest_id),'roomId':str(room_id),'empId':'','checkInDate':date.today()+timedelta(days=2),'checkOutDate':date.today()+timedelta(days=3),'numGuests':1},SimpleNamespace(id=str(ObjectId()),role='staff'))
        collections['bookings'].insert_one.assert_not_called()

    def test_server_calculates_stay_price_and_fee(self):
        guest_id,room_id,room_type_id,staff_id=ObjectId(),ObjectId(),ObjectId(),ObjectId()
        collections={'rooms':Mock(),'bookings':Mock(),'guests':Mock(),'room_types':Mock(),'users':Mock()}
        collections['rooms'].find_one.return_value={'_id':room_id,'typeId':room_type_id,'capacity':2,'status':'Available'}
        collections['bookings'].find_one.return_value=None;collections['guests'].find_one.return_value={'_id':guest_id}
        collections['room_types'].find_one.return_value={'_id':room_type_id,'basePrice':1000}
        collections['bookings'].insert_one.return_value=SimpleNamespace(inserted_id=ObjectId())
        start=date.today()+timedelta(days=2);end=start+timedelta(days=2)
        with patch('hotel.services.bookings.collection',side_effect=lambda name:collections[name]):
            create_booking({'guestId':str(guest_id),'roomId':str(room_id),'empId':str(staff_id),'checkInDate':start,'checkOutDate':end,'numGuests':1},SimpleNamespace(id=str(staff_id),role='staff'))
        inserted=collections['bookings'].insert_one.call_args.args[0]
        self.assertEqual(inserted['priceBreakdown']['roomSubtotal'],2000)
        self.assertEqual(inserted['priceBreakdown']['taxesAndFees'],100)
        self.assertEqual(inserted['totalAmount'],2100)
