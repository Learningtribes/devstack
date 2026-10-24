"""Exercise real Pillow validation, transformation and filesystem storage."""
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from openedx.core.djangoapps.profile_images.images import (
    validate_uploaded_image, create_profile_images, remove_profile_images, _user_friendly_size,
)
from openedx.core.djangoapps.profile_images.exceptions import ImageValidationError

class ImageTests(unittest.TestCase):
    def image_file(self, name='portrait.png', content_type='image/png'):
        data=BytesIO()
        Image.new('RGBA',(180,100),(100,150,200,255)).save(data,format='PNG')
        return SimpleUploadedFile(name,data.getvalue(),content_type=content_type)

    @override_settings(PROFILE_IMAGE_MIN_BYTES=1,PROFILE_IMAGE_MAX_BYTES=1024*1024)
    def test_storage_round_trip(self):
        uploaded=self.image_file()
        validate_uploaded_image(uploaded)
        self.assertEqual(uploaded.tell(),0)
        with tempfile.TemporaryDirectory(prefix='py313-profile-') as directory:
            config={'class':'django.core.files.storage.FileSystemStorage',
                    'options':{'location':directory,'base_url':'/profile/'}}
            with override_settings(PROFILE_IMAGE_BACKEND=config):
                names={32:'portrait_32.jpg',64:'portrait_64.jpg'}
                create_profile_images(uploaded,names)
                for size,name in names.items():
                    with Image.open(Path(directory)/name) as output:
                        self.assertEqual(output.size,(size,size))
                        self.assertEqual(output.mode,'RGB')
                        self.assertEqual(output.format,'JPEG')
                remove_profile_images(names)
                self.assertEqual(list(Path(directory).iterdir()),[])

    @override_settings(PROFILE_IMAGE_MIN_BYTES=1,PROFILE_IMAGE_MAX_BYTES=1024*1024)
    def test_rejects_extension_mime_and_magic_mismatch(self):
        for upload in [self.image_file('portrait.exe'),self.image_file(content_type='image/jpeg'),
                       SimpleUploadedFile('portrait.png',b'not-a-png',content_type='image/png')]:
            with self.assertRaises(ImageValidationError):
                validate_uploaded_image(upload)

    def test_large_size_error_message_is_bounded(self):
        self.assertIn('MB',_user_friendly_size(1024**4))

result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ImageTests))
if not result.wasSuccessful(): raise SystemExit(1)
