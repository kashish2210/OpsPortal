"""Authentication, roles and the server-rendered auth pages."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Role
from .tokens import email_verification_token

User = get_user_model()


class UserModelTests(TestCase):
    def test_email_is_normalised_to_lowercase(self):
        user = User.objects.create_user("bob", "BOB@Example.COM", "pw")
        self.assertEqual(user.email, "bob@example.com")

    def test_create_user_requires_an_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("bob", "", "pw")

    def test_superuser_defaults_to_the_admin_role(self):
        user = User.objects.create_superuser("root", "root@example.com", "pw")
        self.assertEqual(user.role, Role.ADMIN)
        self.assertTrue(user.is_admin_role)

    def test_display_name_and_initials(self):
        user = User.objects.create_user(
            "rsharma", "r@example.com", "pw", first_name="Riya", last_name="Sharma"
        )
        self.assertEqual(user.display_name, "Riya Sharma")
        self.assertEqual(user.initials, "RS")

    def test_initials_fall_back_to_the_username(self):
        user = User.objects.create_user("zed", "z@example.com", "pw")
        self.assertEqual(user.initials, "ZE")


class LoginAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            "riya", "riya@example.com", "Str0ng!pass", role=Role.SALES
        )

    def test_login_with_username(self):
        response = self.client.post(
            "/api/auth/login/", {"username": "riya", "password": "Str0ng!pass"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], Role.SALES)
        self.assertNotIn("password", response.data["user"])

    def test_login_with_email(self):
        response = self.client.post(
            "/api/auth/login/", {"username": "RIYA@example.com", "password": "Str0ng!pass"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/login/", {"username": "riya", "password": "nope"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "validation_error")

    def test_deactivated_account_gets_a_specific_message(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            "/api/auth/login/", {"username": "riya", "password": "Str0ng!pass"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("deactivated", str(response.data["error"]).lower())

    def test_access_token_carries_the_role_claim(self):
        access = self.client.post(
            "/api/auth/login/", {"username": "riya", "password": "Str0ng!pass"}, format="json"
        ).data["access"]

        from rest_framework_simplejwt.tokens import AccessToken

        self.assertEqual(AccessToken(access)["role"], Role.SALES)

    def test_refresh_returns_a_new_access_token(self):
        refresh = self.client.post(
            "/api/auth/login/", {"username": "riya", "password": "Str0ng!pass"}, format="json"
        ).data["refresh"]

        response = self.client.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_logout_blacklists_the_refresh_token(self):
        tokens = self.client.post(
            "/api/auth/login/", {"username": "riya", "password": "Str0ng!pass"}, format="json"
        ).data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        self.assertEqual(
            self.client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json").status_code,
            205,
        )
        self.assertEqual(
            self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code,
            401,
        )

    def test_me_endpoint(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "riya")

    def test_me_endpoint_updates_the_profile_but_not_the_role(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            "/api/auth/me/", {"first_name": "Riya", "role": Role.ADMIN}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["first_name"], "Riya")
        self.assertEqual(response.data["role"], Role.SALES, "role must not be self-assignable")

    def test_change_password(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/auth/change-password/",
            {"old_password": "Str0ng!pass", "new_password": "An0ther!pass"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("An0ther!pass"))

    def test_change_password_rejects_a_wrong_current_password(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/auth/change-password/",
            {"old_password": "wrong", "new_password": "An0ther!pass"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_change_password_enforces_the_validators(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/auth/change-password/",
            {"old_password": "Str0ng!pass", "new_password": "123"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_session_token_handoff(self):
        self.client.login(username="riya", password="Str0ng!pass")
        response = self.client.post("/api/auth/session-token/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["username"], "riya")

    def test_session_token_requires_a_session(self):
        self.assertEqual(self.client.post("/api/auth/session-token/").status_code, 401)


class UserAdminAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user("boss", "boss@example.com", "pw", role=Role.ADMIN)
        self.sales = User.objects.create_user("riya", "riya@example.com", "pw", role=Role.SALES)

    def test_only_admins_may_list_users(self):
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.get("/api/users/").status_code, 403)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/users/").status_code, 200)

    def test_admin_can_create_a_user_with_a_role(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/users/",
            {
                "username": "imran",
                "email": "imran@example.com",
                "role": Role.WAREHOUSE,
                "password": "Str0ng!pass",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(User.objects.get(username="imran").check_password("Str0ng!pass"))

    def test_creating_a_user_without_a_password_fails(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/users/", {"username": "x", "email": "x@example.com", "role": Role.SALES},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data["error"]["details"])

    def test_weak_passwords_are_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/users/",
            {"username": "x", "email": "x@example.com", "role": Role.SALES, "password": "12345"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_deactivates_instead_of_removing(self):
        self.client.force_authenticate(self.admin)
        self.client.delete(f"/api/users/{self.sales.pk}/")
        self.sales.refresh_from_db()
        self.assertFalse(self.sales.is_active)
        self.assertTrue(User.objects.filter(pk=self.sales.pk).exists())

    def test_admins_cannot_deactivate_themselves(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"/api/users/{self.admin.pk}/deactivate/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "cannot_deactivate_self")

    def test_roles_endpoint_is_open_to_any_authenticated_user(self):
        self.client.force_authenticate(self.sales)
        response = self.client.get("/api/users/roles/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({r["value"] for r in response.data}, set(Role.values))


class AuthPageTests(TestCase):
    """Every server-rendered auth page must render with the sketch theme."""

    def setUp(self):
        self.user = User.objects.create_user(
            "riya", "riya@example.com", "Str0ng!pass", role=Role.SALES
        )

    def test_login_page_renders(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        # Match without the extension: with DEBUG=False WhiteNoise serves the
        # hashed name (css/sketch.<hash>.css).
        self.assertContains(response, "css/sketch")
        self.assertContains(response, "Username or e-mail")
        self.assertContains(response, "Forgot password")

    def test_login_works_with_username_and_with_email(self):
        for identifier in ("riya", "riya@example.com"):
            with self.subTest(identifier=identifier):
                self.client.logout()
                response = self.client.post(
                    reverse("accounts:login"),
                    {"username": identifier, "password": "Str0ng!pass"},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("accounts:profile"))

    def test_bad_credentials_show_a_friendly_error(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "riya", "password": "nope"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "did not match any account")

    def test_root_redirects_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:login"))

    def test_signup_creates_a_sales_user_and_signs_them_in(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "newbie",
                "email": "newbie@example.com",
                "first_name": "New",
                "password1": "Str0ng!pass2",
                "password2": "Str0ng!pass2",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username="newbie")
        self.assertEqual(created.role, Role.SALES)
        self.assertEqual(len(mail.outbox), 1, "a verification e-mail should be sent")

    def test_signup_rejects_a_duplicate_email(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "clash",
                "email": "RIYA@example.com",
                "first_name": "Clash",
                "password1": "Str0ng!pass2",
                "password2": "Str0ng!pass2",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    @override_settings(SIGNUP_OPEN=False)
    def test_signup_can_be_closed(self):
        response = self.client.get(reverse("accounts:signup"))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "registration/signup_closed.html")

    def test_logout_confirmation_then_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 200)

        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/logged_out.html")

    def test_password_reset_flow_sends_a_working_link(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "riya@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

        body = mail.outbox[0].body
        link = [word for word in body.split() if "/password/reset/key/" in word][0]
        path = link.split("://")[-1].split("/", 1)[-1]

        follow = self.client.get(f"/{path}", follow=True)
        self.assertEqual(follow.status_code, 200)
        self.assertTemplateUsed(follow, "registration/password_reset_confirm.html")

    def test_password_reset_done_and_complete_pages_render(self):
        for name in ("accounts:password_reset_done", "accounts:password_reset_complete"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_password_change_requires_login(self):
        response = self.client.get(reverse("accounts:password_change"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:password_change")).status_code, 200)

    def test_password_change_works(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "Str0ng!pass",
                "new_password1": "Rotated!pass9",
                "new_password2": "Rotated!pass9",
            },
        )
        self.assertRedirects(response, reverse("accounts:password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Rotated!pass9"))

    def test_password_set_redirects_when_a_password_already_exists(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:password_set"))
        self.assertRedirects(response, reverse("accounts:password_change"))

    def test_password_set_page_for_an_account_without_a_password(self):
        passwordless = User.objects.create(username="ghost", email="ghost@example.com")
        passwordless.set_unusable_password()
        passwordless.save()

        self.client.force_login(passwordless)
        self.assertEqual(self.client.get(reverse("accounts:password_set")).status_code, 200)

    def test_email_page_and_resend(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:email")).status_code, 200)

        response = self.client.post(reverse("accounts:email"), {"action_resend": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_changing_the_email_marks_it_unverified(self):
        self.user.mark_email_verified()
        self.client.force_login(self.user)

        self.client.post(reverse("accounts:email"), {"email": "new@example.com"})
        self.user.refresh_from_db()

        self.assertEqual(self.user.email, "new@example.com")
        self.assertFalse(self.user.is_email_verified)
        self.assertEqual(len(mail.outbox), 1)

    def test_email_confirmation_link(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = email_verification_token.make_token(self.user)
        url = reverse("accounts:email_confirm", kwargs={"uidb64": uidb64, "token": token})

        # GET only shows the confirm button - link scanners must not verify.
        self.client.get(url)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

        self.client.post(url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_a_used_confirmation_token_stops_working(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = email_verification_token.make_token(self.user)
        url = reverse("accounts:email_confirm", kwargs={"uidb64": uidb64, "token": token})

        self.client.post(url)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)

    def test_static_auth_pages_render(self):
        for name in ("accounts:verification_sent", "accounts:account_inactive", "accounts:signup_closed"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_verified_email_required_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:verified_email_required"))
        self.assertEqual(response.status_code, 200)

        self.user.mark_email_verified()
        response = self.client.get(reverse("accounts:verified_email_required"))
        self.assertRedirects(response, reverse("accounts:profile"))

    def test_profile_page_links_to_the_spa(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/auth/handoff")

    def test_profile_can_be_updated(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("accounts:profile"),
            {"first_name": "Riya", "last_name": "Sharma", "phone": "9820011223", "department": "Sales"},
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "Riya Sharma")


class HealthCheckTests(TestCase):
    def test_health_endpoint_is_public(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
