from django.core.management.base import BaseCommand
from hotel.db import collection
from hotel.encryption import protect_guest_fields


class Command(BaseCommand):
    help = 'Encrypt plaintext guest addresses and ID proof numbers in MongoDB.'

    def handle(self, *args, **options):
        guests = collection('guests')
        changed = 0
        for row in guests.find({}, {'address': 1, 'idProofNo': 1}):
            protected = protect_guest_fields(row)
            updates = {
                key: value for key, value in protected.items()
                if key in {'address', 'idProofNo'} and value != row.get(key)
            }
            if updates:
                guests.update_one({'_id': row['_id']}, {'$set': updates})
                changed += 1
        self.stdout.write(self.style.SUCCESS(f'Encrypted guest fields for {changed} records.'))
