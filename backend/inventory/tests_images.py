"""Tests for product image upload (bonus: S3-backed media)."""

import io
import shutil
import tempfile
from decimal import Decimal

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


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
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
        row = next(
            r for r in self.client.get("/api/products/").data["results"] if r["id"] == self.product.pk
        )
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
        self.assertEqual(
            self.client.delete(f"/api/products/{self.product.pk}/image/").status_code, 200
        )

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


class S3ConfigurationTests(TestCase):
    """The storage backend is selected purely by env, with no code changes."""

    def test_local_storage_is_the_default(self):
        from django.conf import settings

        self.assertFalse(settings.USE_S3)
        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )

    def test_s3_backend_is_importable(self):
        """Guards against a missing django-storages/boto3 dependency."""
        from storages.backends.s3 import S3Storage

        self.assertTrue(callable(S3Storage))
