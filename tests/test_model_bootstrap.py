import base64
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import model_bootstrap as model


def ready():
    return dict(store_session_authenticated=True,authorization_request_attempted=True,http_status=200,
                apple_failure_present=False,keybag_present=True,commerce_import_call_returned=True,
                state_observation_after={"root_status":"observed","root":{"files":{"fpsd_sidb":{"status":"regular_nonempty"}}}})


def setup(path):
    return json.dumps(dict(schema="unfairplay-setup-v1",success=True,plaintext_verified=True,
                           encrypted_images=2,decrypted_pages=3,model=str(path),
                           selector="PRIVATE_SYNTHETIC_SELECTOR")).encode()


def sealed():
    return json.dumps(dict(schema="ipa-lab-github-sealed-model-v1",
        repository="zwthys-cyber/ipa-decrypt-lab",secret_name="FAIRPLAY_MODEL_B64",
        key_id="3380204578043523366",encrypted_value=base64.b64encode(b"x"*96).decode())).encode()


class BootstrapTests(unittest.TestCase):
    def test_state_file_must_be_observed_as_root(self):
        self.assertTrue(model.state_ready(ready()))
        value=ready()
        value["state_observation_after"]["root"]["files"]["fpsd_sidb"]["status"]="permission_denied"
        self.assertFalse(model.state_ready(value))
        self.assertFalse(model.state_ready({}))

    def test_service_response_alone_is_not_ready(self):
        for field,new in (("http_status",401),("apple_failure_present",True),("keybag_present",False),
                          ("commerce_import_call_returned",False),("store_session_authenticated",False)):
            value=ready()
            value[field]=new
            self.assertFalse(model.state_ready(value))

    def test_no_state_stops_before_downloader(self):
        with patch.object(model,"enroll",return_value={}),patch.object(model,"download_original") as download:
            result=model.bootstrap("login","native","download","engine","sealer")
        download.assert_not_called()
        self.assertEqual(result["status"],"enrollment_state_unavailable")

    def test_archive_is_an_extracted_candidate_not_claimed_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            ipa=root/"app.ipa"
            with zipfile.ZipFile(ipa,"w") as archive:
                archive.writestr("Payload/Test.app/Info.plist",plistlib.dumps({"CFBundleExecutable":"Test"}))
                archive.writestr("Payload/Test.app/Test",b"PRIVATE_SYNTHETIC_EXECUTABLE")
                archive.writestr("Payload/Test.app/SC_Info/Test.sinf",b"PRIVATE_SYNTHETIC_LICENSE")
            app=model.candidate_app(ipa,root/"output")
            self.assertEqual(app.name,"Test.app")

    def test_archive_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            ipa=root/"bad.ipa"
            with zipfile.ZipFile(ipa,"w") as archive:
                archive.writestr("../private",b"PRIVATE")
            with self.assertRaises(ValueError):
                model.candidate_app(ipa,root/"out")

    def test_model_path_must_stay_private_and_inside_expected_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            private=root/"model.bin"
            private.write_bytes(b"PRIVATE_SYNTHETIC_MODEL")
            private.chmod(0o600)
            path,summary=model.setup_summary(setup(private),root)
            self.assertEqual(path,private.resolve())
            self.assertNotIn("PRIVATE_SYNTHETIC",json.dumps(summary))
            private.chmod(0o644)
            with self.assertRaises(ValueError):
                model.setup_summary(setup(private),root)
            private.chmod(0o600)
            with self.assertRaises(ValueError):
                model.setup_summary(setup(private),root/"different")

    def test_setup_without_explicit_success_is_rejected(self):
        with self.assertRaises(ValueError):
            model.setup_summary(b'{"schema":"unfairplay-setup-v1","success":false}',Path("/unused"))

    def test_failure_classification_does_not_publish_errors(self):
        result=model.recovery_failure(b"SIDB authentication failure PRIVATE_SYNTHETIC_ACCOUNT")
        self.assertTrue(result["sidb"])
        self.assertTrue(result["authentication"])
        self.assertNotIn("PRIVATE_SYNTHETIC",json.dumps(result))

    def test_sealed_report_is_fixed_to_our_repository_key_and_secret(self):
        value=model.sealed_summary(sealed())
        for field,new in (("repository","attacker/repo"),("secret_name","OTHER"),("key_id","123")):
            bad=dict(value,**{field:new})
            with self.assertRaises(ValueError):
                model.sealed_summary(json.dumps(bad).encode())
        value["private"]="PRIVATE_SYNTHETIC"
        self.assertNotIn("PRIVATE_SYNTHETIC",json.dumps(model.sealed_summary(json.dumps(value).encode())))

    def exercise_recovery(self,verified):
        calls=[]
        def download(binary,ipa):
            ipa.write_bytes(b"PRIVATE_SYNTHETIC_IPA")
            return "original_downloaded"
        def run(argv,env,**kwargs):
            calls.append(argv)
            self.assertNotIn("APPLE_ID",env)
            self.assertNotIn("APPLE_PASSWORD",env)
            if argv[0]=="/usr/bin/sudo":
                directory=Path(argv[argv.index("--model-dir")+1])
                path=directory/"model.bin"
                path.write_bytes(b"PRIVATE_SYNTHETIC_MODEL")
                path.chmod(0o600)
                return 0,setup(path),b"PRIVATE_SYNTHETIC_OUTPUT"
            return 0,sealed(),b""
        previous=os.environ.get("FAIRPLAY_MODEL_B64")
        with patch.object(model,"enroll",return_value=ready()), \
                patch.object(model,"download_original",side_effect=download), \
                patch.object(model,"candidate_app",return_value=Path("/synthetic/app")), \
                patch.object(model,"run_private",side_effect=run), \
                patch.object(model,"verify",return_value={"decryption_proven":verified,"plaintext_verified":verified}):
            result=model.bootstrap("login","native","download","engine","sealer")
        self.assertEqual(os.environ.get("FAIRPLAY_MODEL_B64"),previous)
        self.assertNotIn("PRIVATE_SYNTHETIC",json.dumps(result))
        return result,calls

    def test_unverified_plaintext_never_emits_model(self):
        result,calls=self.exercise_recovery(False)
        self.assertEqual(result["status"],"model_plaintext_not_verified")
        self.assertEqual(len(calls),1)
        self.assertNotIn("sealed_model",result)

    def test_verified_model_is_sealed_without_publishing_plaintext(self):
        result,calls=self.exercise_recovery(True)
        self.assertEqual(result["status"],"model_recovered_and_verified")
        self.assertTrue(result["plaintext_verified"])
        self.assertFalse(result["model_plaintext_published"])
        self.assertEqual(result["app_input_kind"],"extracted_ipa_candidate")
        self.assertEqual(len(calls),2)


if __name__=="__main__":
    unittest.main()
