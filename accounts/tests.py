from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from .models import Membership, Profile


class AccountsModelTests(TestCase):
    def test_profile_created_for_new_user(self):
        user = get_user_model().objects.create_user(username="alice", password="pass")
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_membership_unique_per_user(self):
        user = get_user_model().objects.create_user(username="bob", password="pass")
        Membership.objects.create(user=user, role=Membership.ROLE_ADMIN)
        with self.assertRaises(IntegrityError):
            Membership.objects.create(user=user, role=Membership.ROLE_STAFF)
