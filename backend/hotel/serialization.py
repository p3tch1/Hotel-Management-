from bson import ObjectId
from datetime import datetime, date
from rest_framework.exceptions import ValidationError
from hotel.encryption import decrypt_value

def clean(value):
    if isinstance(value, str): return decrypt_value(value)
    if isinstance(value, ObjectId): return str(value)
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, list): return [clean(v) for v in value]
    if isinstance(value, dict): return {k: clean(v) for k, v in value.items() if k != '_id'}
    return value

def document(value):
    if not value: return None
    result = clean(value)
    result['id'] = str(value['_id'])
    return result

def documents(values):
    return [document(v) for v in values]

def oid(value):
    if not ObjectId.is_valid(str(value)):
        raise ValidationError('Invalid record id.')
    return ObjectId(str(value))
