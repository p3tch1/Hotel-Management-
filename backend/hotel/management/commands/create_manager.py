from datetime import datetime, timezone
from getpass import getpass
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from hotel.db import collection


class Command(BaseCommand):
    help = 'Create the initial manager account without using public demo credentials.'

    def handle(self, *args, **options):
        name = input('Manager name: ').strip()
        email = input('Manager email: ').strip().lower()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError('Enter a valid email address.') from exc
        if not name:
            raise CommandError('Manager name is required.')
        users = collection('users')
        if users.find_one({'email': email}):
            raise CommandError('An account with that email already exists.')
        password = getpass('Manager password (minimum 12 characters): ')
        confirmation = getpass('Confirm password: ')
        if len(password) < 12:
            raise CommandError('Manager password must contain at least 12 characters.')
        if password != confirmation:
            raise CommandError('The passwords do not match.')
        row = {
            'name': name,
            'email': email,
            'phone': '',
            'passwordHash': make_password(password),
            'role': 'manager',
            'designation': 'Property Manager',
            'active': True,
            'createdAt': datetime.now(timezone.utc),
        }
        users.insert_one(row)
        self.stdout.write(self.style.SUCCESS(f'Manager account created for {email}.'))
