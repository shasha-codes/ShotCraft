import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app import image_storage, main


FILENAME = "a" * 32 + ".jpg"
IMAGE = b"\xff\xd8test-image\xff\xd9"


class GeneratedImageStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.output_patch = patch.object(image_storage, "OUTPUT_DIR", Path(self.directory.name))
        self.output_patch.start()

    def tearDown(self):
        self.output_patch.stop()
        self.directory.cleanup()

    def test_local_only_when_bucket_not_configured(self):
        with patch.dict(os.environ, {"SHOTCRAFT_IMAGE_S3_BUCKET": ""}):
            with patch.object(image_storage, "_client") as client:
                url = image_storage.save_generated_image(FILENAME, IMAGE)
                self.assertEqual(url, f"/generated/{FILENAME}")
                self.assertEqual(image_storage.load_generated_image(FILENAME), IMAGE)
                client.assert_not_called()

    def test_uploads_private_object_and_keeps_local_mirror(self):
        s3 = Mock()
        with patch.dict(os.environ, {"SHOTCRAFT_IMAGE_S3_BUCKET": "images", "SHOTCRAFT_IMAGE_S3_PREFIX": "shoots/generated/"}):
            with patch.object(image_storage, "_client", return_value=s3):
                image_storage.save_generated_image(FILENAME, IMAGE)
        s3.put_object.assert_called_once_with(
            Bucket="images", Key=f"shoots/generated/{FILENAME}", Body=IMAGE, ContentType="image/jpeg"
        )
        self.assertEqual((image_storage.OUTPUT_DIR / FILENAME).read_bytes(), IMAGE)

    def test_upload_failure_uses_local_fallback(self):
        s3 = Mock()
        s3.put_object.side_effect = ConnectionError("S3 unavailable")
        s3.get_object.side_effect = ConnectionError("S3 unavailable")
        with patch.dict(os.environ, {"SHOTCRAFT_IMAGE_S3_BUCKET": "images"}):
            with patch.object(image_storage, "_client", return_value=s3):
                image_storage.save_generated_image(FILENAME, IMAGE)
                self.assertEqual(image_storage.load_generated_image(FILENAME), IMAGE)

    def test_reads_s3_copy_when_available(self):
        s3 = Mock()
        s3.get_object.return_value = {"Body": io.BytesIO(b"from-s3")}
        with patch.dict(os.environ, {"SHOTCRAFT_IMAGE_S3_BUCKET": "images"}):
            with patch.object(image_storage, "_client", return_value=s3):
                self.assertEqual(image_storage.load_generated_image(FILENAME), b"from-s3")

    def test_rejects_invalid_filenames_and_returns_404(self):
        with self.assertRaises(ValueError):
            image_storage.save_generated_image("../secret.jpg", IMAGE)
        with patch.dict(os.environ, {"SHOTCRAFT_IMAGE_S3_BUCKET": ""}):
            self.assertIsNone(image_storage.load_generated_image("../secret.jpg"))
            with self.assertRaises(HTTPException) as error:
                main.generated_image(FILENAME)
            self.assertEqual(error.exception.status_code, 404)

    def test_route_serves_stable_local_url(self):
        with patch.dict(os.environ, {"SHOTCRAFT_IMAGE_S3_BUCKET": ""}):
            image_storage.save_generated_image(FILENAME, IMAGE)
            response = main.generated_image(FILENAME)
        self.assertEqual(response.body, IMAGE)
        self.assertEqual(response.media_type, "image/jpeg")


if __name__ == "__main__":
    unittest.main()
