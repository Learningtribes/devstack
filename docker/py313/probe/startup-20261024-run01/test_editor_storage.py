"""Real Django widget rendering and storage configuration, no external I/O."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from django.conf import settings
settings.configure(SECRET_KEY='ephemeral-unit-only', USE_I18N=False,
    INSTALLED_APPS=[],
    COURSE_IMPORT_EXPORT_STORAGE='django.core.files.storage.FileSystemStorage',
    COURSE_IMPORT_EXPORT_BUCKET='unit-course-archives', AWS_STORAGE_BUCKET_NAME='unit-default',
    TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates',
        'OPTIONS':{'loaders':[('django.template.loaders.locmem.Loader', {
            'wiki/includes/editor_widget.html':'<textarea{{ attrs }}>{{ content }}</textarea>'})]}}])
import django
django.setup()
from django.core.files.base import ContentFile

def load(name, relative):
    path=Path('/edx/app/edxapp/edx-platform')/relative
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class EditorStorageTests(unittest.TestCase):
    def test_widget_django_renderer_protocol_and_escaping(self):
        mod=load('wiki_editor_runtime', 'lms/djangoapps/course_wiki/editors.py')
        widget=mod.CodeMirrorWidget()
        result=widget.render('body', '<script>课程</script>', renderer=object())
        self.assertIn('&lt;script&gt;课程&lt;/script&gt;',result)
        self.assertIn('name="body"',result)
        attrs={'id':'course-body'}
        self.assertIn('id="course-body"',widget.render('body','text',attrs=attrs))
        self.assertEqual(attrs,{'id':'course-body'})
    def test_archive_storage_configuration_and_file_persistence(self):
        mod=load('course_archive_storage_runtime', 'cms/djangoapps/contentstore/storage.py')
        storage=mod.ImportExportS3Storage()
        self.assertEqual(storage.bucket_name,'unit-course-archives')
        self.assertIsNone(storage.custom_domain)
        self.assertTrue(storage.querystring_auth)
        from django.core.files.storage import FileSystemStorage
        with tempfile.TemporaryDirectory() as directory:
            storage=FileSystemStorage(location=directory)
            name=storage.save('课程.tar.gz',ContentFile(b'archive-bytes'))
            with FileSystemStorage(location=directory).open(name,'rb') as result:
                self.assertEqual(result.read(),b'archive-bytes')
if __name__=='__main__': unittest.main(verbosity=2)
