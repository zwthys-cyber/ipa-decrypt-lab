import io
import plistlib
import sys
import tempfile
import unittest
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from app_presentation import component, filename, jpeg, archive_thumbnail, thumbnail, store_thumbnail
from telegram_api import Telegram, APIError
try:
    from PIL import Image
except ImportError:
    Image=None

class PresentationTests(unittest.TestCase):
    def test_unicode_name_real_version_and_safe_path(self):
        self.assertEqual(filename({"display_name":"微信","version":"8.0.80"},"12345"),"微信_8.0.80.ipa")
        result=filename({"display_name":"../../a\\b\n\u202e","version":"../9"},"12345")
        self.assertNotIn("/",result)
        self.assertNotIn("\\",result)
        self.assertNotIn("\n",result)
        self.assertNotIn("\u202e",result)
        self.assertLess(len(filename({"display_name":"界"*500,"version":"1"*500},"12345").encode()),200)
        self.assertEqual(filename({},"12345"),"12345_unknown.ipa")

    def test_icon_failure_is_optional(self):
        with patch("app_presentation.archive_thumbnail",side_effect=ValueError("private")), \
             patch("app_presentation.store_thumbnail",return_value=None):
            self.assertIsNone(thumbnail("not-a-file","12345"))

    def test_store_icon_rejects_arbitrary_url_without_fetch(self):
        for url in ("http://a.mzstatic.com/x","https://evil.test/x","https://a.mzstatic.com.evil.test/x",
                    "https://user@a.mzstatic.com/x"):
            with patch("app_preflight.check_app",return_value={"artworkUrl512":url}), \
                 patch("app_presentation.urllib.request.build_opener") as opener:
                self.assertIsNone(store_thumbnail("12345"))
                opener.assert_not_called()

    @unittest.skipIf(Image is None,"Pillow runtime tested by VPS release on Ubuntu and Debian")
    def test_ipa_icon_becomes_bounded_jpeg_without_metadata(self):
        raw=io.BytesIO()
        Image.new("RGBA",(512,512),(30,80,200,120)).save(raw,"PNG")
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"test.ipa"
            info={"CFBundleIcons":{"CFBundlePrimaryIcon":{"CFBundleIconFiles":["AppIcon60x60"]}}}
            with zipfile.ZipFile(path,"w") as archive:
                archive.writestr("Payload/Test.app/Info.plist",plistlib.dumps(info))
                archive.writestr("Payload/Test.app/AppIcon60x60@3x.png",raw.getvalue())
            result=archive_thumbnail(path)
            self.assertLess(len(result),200000)
            with Image.open(io.BytesIO(result)) as image:
                self.assertEqual(image.format,"JPEG")
                self.assertEqual(image.size,(320,320))
                self.assertNotIn("exif",image.info)
            with patch("app_presentation.store_thumbnail") as fallback:
                self.assertIsNotNone(thumbnail(path,"12345"))
                fallback.assert_not_called()

    @unittest.skipIf(Image is None,"Pillow runtime tested by VPS release on Ubuntu and Debian")
    def test_oversized_pixels_and_bytes_rejected(self):
        raw=io.BytesIO()
        Image.new("RGB",(2049,1)).save(raw,"PNG")
        self.assertIsNone(jpeg(raw.getvalue()))
        self.assertIsNone(jpeg(b"x"*(4*1024*1024+1)))

    def test_multipart_only_contains_small_thumbnail_and_local_file_reference(self):
        bot=Telegram("123456:"+"A"*35,"http://127.0.0.1:8081")
        bot._request=Mock(return_value={"message_id":1})
        icon=b"\xff\xd8synthetic-jpeg\xff\xd9"
        payload={"chat_id":12345,"document":"file:///private/%E5%BE%AE%E4%BF%A1_8.0.80.ipa",
                 "caption":"微信 8.0.80","disable_content_type_detection":True}
        bot.document(payload,icon,timeout=1200)
        method,data,content_type,timeout=bot._request.call_args.args
        self.assertEqual(method,"sendDocument")
        self.assertEqual(timeout,1200)
        message=BytesParser(policy=default).parsebytes(("Content-Type: "+content_type+"\r\n\r\n").encode()+data)
        parts={p.get_param("name",header="content-disposition"):p for p in message.iter_parts()}
        self.assertEqual(parts["document"].get_payload(decode=True).decode(),payload["document"])
        self.assertEqual(parts["thumbnail"].get_payload(decode=True),b"attach://app_icon")
        self.assertEqual(parts["app_icon"].get_payload(decode=True),icon)
        self.assertEqual(parts["app_icon"].get_filename(),"icon.jpg")
        self.assertLess(len(data),10000)

    def test_send_failure_never_retries_without_icon(self):
        bot=Telegram("123456:"+"A"*35,"http://127.0.0.1:8081")
        bot._request=Mock(side_effect=APIError("telegram_transport_unknown"))
        with self.assertRaises(APIError):
            bot.document({"document":"file:///private/test.ipa"},b"\xff\xd8test",timeout=20)
        bot._request.assert_called_once()

    def test_missing_icon_uses_existing_document_transport(self):
        bot=Telegram("123456:"+"A"*35,"http://127.0.0.1:8081")
        bot.call=Mock(return_value={"message_id":1})
        payload={"document":"file:///private/QQ_9.3.55.ipa"}
        bot.document(payload,None,timeout=40)
        bot.call.assert_called_once_with("sendDocument",payload,timeout=40)
