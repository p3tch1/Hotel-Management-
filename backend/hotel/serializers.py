from datetime import date
from rest_framework import serializers

class RegisterSerializer(serializers.Serializer):
    firstName = serializers.CharField(max_length=50)
    lastName = serializers.CharField(max_length=50, required=False, allow_blank=True)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(min_length=10, write_only=True)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class BookingSerializer(serializers.Serializer):
    guestId = serializers.CharField()
    roomId = serializers.CharField()
    empId = serializers.CharField(required=False, allow_blank=True)
    checkInDate = serializers.DateField()
    checkOutDate = serializers.DateField()
    numGuests = serializers.IntegerField(min_value=1, max_value=10)

    def validate(self, attrs):
        if attrs['checkOutDate'] <= attrs['checkInDate']:
            raise serializers.ValidationError({'checkOutDate': 'Check-out must be after check-in.'})
        if attrs['checkInDate'] < date.today():
            raise serializers.ValidationError({'checkInDate': 'Check-in cannot be in the past.'})
        return attrs

class RoomSerializer(serializers.Serializer):
    roomNumber = serializers.CharField(max_length=12)
    floorNo = serializers.IntegerField(min_value=0)
    typeId = serializers.CharField()
    status = serializers.ChoiceField(choices=['Available','Occupied','Maintenance','Cleaning','Inspected','Out of Service'], required=False)
    capacity = serializers.IntegerField(min_value=1, max_value=10, required=False)
    amenities = serializers.ListField(child=serializers.CharField(), required=False)
    images = serializers.ListField(child=serializers.URLField(), required=False)

class RoomTypeSerializer(serializers.Serializer):
    typeName = serializers.CharField(max_length=60)
    description = serializers.CharField(required=False, allow_blank=True)
    basePrice = serializers.FloatField(min_value=0.01)
    maxOccupancy = serializers.IntegerField(min_value=1, max_value=10)
    amenities = serializers.ListField(child=serializers.CharField(max_length=60), required=False)

class ServiceCatalogSerializer(serializers.Serializer):
    serviceName = serializers.CharField(max_length=100)
    category = serializers.ChoiceField(choices=['Dining','Wellness','Transport','Laundry','Other'])
    price = serializers.FloatField(min_value=0)
    description = serializers.CharField(required=False, allow_blank=True)

class ServiceRequestSerializer(serializers.Serializer):
    bookingId = serializers.CharField(required=False, allow_blank=True)
    roomId = serializers.CharField()
    category = serializers.ChoiceField(choices=['Housekeeping','Extra Towels','Room Service','Maintenance','Other'])
    description = serializers.CharField(max_length=1000)
    priority = serializers.ChoiceField(choices=['Low','Normal','High','Urgent'], default='Normal')

class PaymentSerializer(serializers.Serializer):
    bookingId = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    paymentMethod = serializers.ChoiceField(choices=['Cash','Card','UPI','Net Banking'])

class StatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['New','Pending','In Progress','Completed','Cancelled'])
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)
