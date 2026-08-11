"""Tests for product image upload (bonus: S3-backed media)."""

import io
import os
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from .models import Product, product_image_path
from .tests import make_product

User = get_user_model()

#: Keep uploaded test files out of the real media directory.
TEMP_MEDIA = tempfile.mkdtemp(prefix="opsportal-test-media-")

#: Force local storage for the upload tests. Without this the suite would use
#: whatever MEDIA_STORAGE the developer's .env selects - and on a machine
#: configured for Cloudinary or S3, running the tests would upload to the real
#: account over the network.
LOCAL_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def make_image_upload(name="photo.jpg", size=(64, 64), fmt="JPEG", content_type="image/jpeg"):
    """Build a genuine in-memory image file (Pillow validates the bytes)."""
    buffer = io.BytesIO()
    Image.new("RGB", size, (210, 191, 174)).save(buffer, format=fmt)
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type=content_type)


class ProductImagePathTests(TestCase):
    def test_path_is_namespaced_by_sku_and_unique(self):
        product = Product(sku="EL-CW15-90")
        first = product_image_path(product, "photo.JPG")
        second = product_image_path(product, "photo.JPG")

        self.assertTrue(first.startswith("products/EL-CW15-90/"))
        self.assertTrue(first.endswith(".jpg"), "extension should be lower-cased")
        self.assertNotEqual(first, second, "re-uploads must not collide")

    def test_slashes_in_the_sku_do_not_escape_the_prefix(self):
        path = product_image_path(Product(sku="A/B"), "x.png")
        self.assertTrue(path.startswith("products/A-B/"))

    def test_missing_extension_falls_back_to_jpg(self):
        self.assertTrue(product_image_path(Product(sku="X"), "noext").endswith(".jpg"))


@override_settings(MEDIA_ROOT=TEMP_MEDIA, STORAGES=LOCAL_STORAGES)
class ProductImageUploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        self.warehouse = User.objects.create_user("wh", "wh@example.com", "pw", role="WAREHOUSE")
        self.sales = User.objects.create_user("sl", "sl@example.com", "pw", role="SALES")
        self.product = make_product(sku="IMG-1", stock=10, unit_price=Decimal("100.00"))

    def test_upload_stores_the_image_and_returns_a_url(self):
        self.client.force_authenticate(self.warehouse)
        response = self.client.post(
            f"/api/products/{self.product.pk}/image/",
            {"image": make_image_upload()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNotNone(response.data["image_url"])
        self.assertIn("products/IMG-1/", response.data["image_url"])

        self.product.refresh_from_db()
        self.assertTrue(self.product.image)
        self.assertEqual(self.product.updated_by, self.warehouse)

    def test_image_url_appears_on_the_list_endpoint(self):
        self.client.force_authenticate(self.warehouse)
        self.client.post(
            f"/api/products/{self.product.pk}/image/",
            {"image": make_image_upload()},
            format="multipart",
        )
        row = next(r for r in self.client.get("/api/products/").data["results"] if r["id"] == self.product.pk)
        self.assertIsNotNone(row["image_url"])

    def test_replacing_an_image_removes_the_previous_file(self):
        self.client.force_authenticate(self.warehouse)
        self.client.post(
            f"/api/products/{self.product.pk}/image/",
            {"image": make_image_upload("first.jpg")},
            format="multipart",
        )
        self.product.refresh_from_db()
        first_name = self.product.image.name
        storage = self.product.image.storage
        self.assertTrue(storage.exists(first_name))

        self.client.post(
            f"/api/products/{self.product.pk}/image/",
            {"image": make_image_upload("second.jpg")},
            format="multipart",
        )
        self.product.refresh_from_db()

        self.assertNotEqual(self.product.image.name, first_name)
        self.assertFalse(storage.exists(first_name), "the old object should be deleted")

    def test_delete_clears_the_image(self):
        self.client.force_authenticate(self.warehouse)
        self.client.post(
            f"/api/products/{self.product.pk}/image/",
            {"image": make_image_upload()},
            format="multipart",
        )
        response = self.client.delete(f"/api/products/{self.product.pk}/image/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["image_url"])
        self.product.refresh_from_db()
        self.assertFalse(self.product.image)

    def test_deleting_when_there_is_no_image_is_a_no_op(self):
        self.client.force_authenticate(self.warehouse)
        self.assertEqual(self.client.delete(f"/api/products/{self.product.pk}/image/").status_code, 200)

    def test_oversized_image_is_rejected(self):
        self.client.force_authenticate(self.warehouse)
        with override_settings(MAX_UPLOAD_SIZE_BYTES=1024):
            response = self.client.post(
                f"/api/products/{self.product.pk}/image/",
                {"image": make_image_upload(size=(600, 600))},
                format="multipart",
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data["error"]["details"])

    def test_non_image_upload_is_rejected(self):
        self.client.force_authenticate(self.warehouse)
        response = self.client.post(
            f"/api/products/{self.product.pk}/image/",
            {"image": SimpleUploadedFile("evil.jpg", b"not really an image", content_type="image/jpeg")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_unsupported_image_type_is_rejected(self):
        self.client.force_authenticate(self.warehouse)
        response = self.client.post(
            f"/api/products/{self.product.pk}/image/",
            {"image": make_image_upload("photo.gif", fmt="GIF", content_type="image/gif")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_sales_role_cannot_upload(self):
        self.client.force_authenticate(self.sales)
        response = self.client.post(
            f"/api/products/{self.product.pk}/image/",
            {"image": make_image_upload()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 403)

    def test_upload_requires_authentication(self):
        response = self.client.post(
            f"/api/products/{self.product.pk}/image/",
            {"image": make_image_upload()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 401)


class MediaStorageConfigurationTests(TestCase):
    """The storage backend is selected purely by env, with no code changes.

    These assert the *wiring*, not which provider happens to be configured on
    this machine - the suite has to pass identically on a laptop set to
    Cloudinary and in CI, where nothing is configured at all.
    """

    def test_media_storage_is_a_recognised_value(self):
        from django.conf import settings

        self.assertIn(settings.MEDIA_STORAGE, ("local", "cloudinary", "s3"))

    def test_every_backend_is_importable(self):
        """Guards against a missing storage dependency in requirements.txt."""
        cloudinary_env = {
            "CLOUDINARY_CLOUD_NAME": "demo",
            "CLOUDINARY_API_KEY": "demo",
            "CLOUDINARY_API_SECRET": "demo",
            "CLOUDINARY_URL": "cloudinary://demo:demo@demo",
        }

        with mock.patch.dict(os.environ, cloudinary_env, clear=False):
            from cloudinary_storage.storage import MediaCloudinaryStorage

        from django.core.files.storage import FileSystemStorage
        from storages.backends.s3 import S3Storage

        for backend in (FileSystemStorage, S3Storage, MediaCloudinaryStorage):
            self.assertTrue(callable(backend), backend)

    def test_the_configured_backend_matches_the_selection(self):
        from django.conf import settings

        expected = {
            "local": "django.core.files.storage.FileSystemStorage",
            "cloudinary": "cloudinary_storage.storage.MediaCloudinaryStorage",
            "s3": "storages.backends.s3.S3Storage",
        }[settings.MEDIA_STORAGE]
        self.assertEqual(settings.STORAGES["default"]["BACKEND"], expected)

    def test_use_s3_is_still_honoured_as_a_legacy_alias(self):
        from django.conf import settings

        # USE_S3=True must keep selecting s3 for anyone on the old variable.
        if settings.USE_S3:
            self.assertEqual(settings.MEDIA_STORAGE, "s3")

    def test_an_unknown_value_is_rejected_loudly(self):
        """A typo in MEDIA_STORAGE should fail at boot, not silently fall back."""
        import importlib

        from django.core.exceptions import ImproperlyConfigured

        with mock.patch.dict(os.environ, {"MEDIA_STORAGE": "dropbox"}):
            with self.assertRaises(ImproperlyConfigured):
                importlib.reload(importlib.import_module("config.settings"))

        # Restore the real module state for the rest of the suite.
        importlib.reload(importlib.import_module("config.settings"))
