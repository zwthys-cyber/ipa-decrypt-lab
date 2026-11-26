"""CI only: synthetic native transport, real ZIP proofs and real age encryption; no Apple network."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch
import task_context as context
import appstore_worker as worker
import cn_profile
import private_process
from private_export import audit, digest, ExportError

def b64(raw):return base64.b64encode(raw).decode()
def image(cryptid):
    h=struct.pack("<8I",0xFEEDFACF,0x0100000C,0,2,1,24,0,0)
    c=struct.pack("<6I",0x2C,24,4096,4096,cryptid,0)
    return (h+c).ljust(8192,b"\0")
def archive(path,cryptid=1,version="1.2.3"):
    with zipfile.ZipFile(path,"w") as z:
        z.writestr("Payload/Demo.app/Info.plist",plistlib.dumps(dict(CFBundleIdentifier="example.synthetic",
            CFBundleExecutable="Demo",CFBundleShortVersionString=version)))
        z.writestr("Payload/Demo.app/Demo",image(cryptid))
        z.writestr("Payload/Demo.app/SC_Info/Demo.sinf",b"synthetic-private-account")
        z.writestr("iTunesMetadata.plist",b"synthetic-private-account")
def model():
    return b64(b"FPSENR2\0"+struct.pack("<II",2,4184)+b"\0"*(4184-16))
def cn_values():
    guid="AABBCCDDEEFF"
    account=dict(email="fixture@example.invalid",store="143465",directoryServicesIdentifier="123456",
        passwordToken="synthetic-session-token",cookie=[],labStoreFront="143465-1")
    value=dict(schema="cn-account-session-v1",email=account["email"],guid=guid,store="143465",
        created=int(time.time()),account=account)
    state=dict(schema="ipa-lab-private-fairplay-state-v1",hardware=b64(bytes.fromhex(guid)),
        files=dict(fpsd_sidb=b64(b"synthetic-checkpoint")))
    return dict(APPLE_CN_ID=value["email"],APPLE_CN_GUID=guid,APPLE_CN_SESSION_B64=b64(json.dumps(value).encode()),
        FAIRPLAY_CN_MODEL_B64=model(),FAIRPLAY_CN_STATE_B64=b64(json.dumps(state).encode()))

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.task=dict(schema="circleci-export-request-v1",job_id="pilot_"+"a"*32,request_id="b"*32,
            run_id="12345678-1234-1234-1234-123456789abc",worker_job_id="23456789-1234-1234-1234-123456789abc",
            source_sha="c"*40,profile="default",target="123456",version="",recipient=context.RECIPIENT,
            deadline=int(time.time())+1800)
        self.env=dict(PATH=os.environ["PATH"],LANG="C.UTF-8",CIRCLECI="true",CIRCLE_PROJECT_USERNAME="zwthys-cyber",
            CIRCLE_PROJECT_REPONAME="ipa-decrypt-lab",CIRCLE_BRANCH=context.BRANCH,CIRCLE_SHA1=self.task["source_sha"],
            CIRCLE_WORKFLOW_JOB_ID=self.task["worker_job_id"],RUNTIME_RUN_ID=self.task["run_id"])
        self.values=dict(APPLE_ID="fixture@example.invalid",APPLE_PASSWORD="synthetic-password",FAIRPLAY_MODEL_B64=model())
        self.calls=[];self.stages=[];self.bad_proof=False;self.bad_version=False;self.mutate_cn=False;self.runtime_bad=False
        self.seen_clean=False

    def loader(self,repo,pins,variant,path):
        path.mkdir()
        for name in ("ApplePackageTool","lab-kbsync","offline-engine"):(path/name).write_text("synthetic-native-stub")
        return dict(schema="circleci-native-fetch-v1",source=pins["source"],variant=variant,
            archive_sha256="bad" if self.runtime_bad else pins["variants"][variant]["archive_sha256"])

    def execute(self,binary,args,env,timeout,root,checkpoint):
        checkpoint();args=list(map(str,args));self.calls.append((Path(binary).name,args,dict(env)))
        self.assertNotIn("GITHUB_ACTIONS",env)
        if Path(binary).name=="age":
            with zipfile.ZipFile(args[-1]) as z:
                self.assertFalse(any("SC_Info" in n or n=="iTunesMetadata.plist" for n in z.namelist()))
                self.assertEqual(z.read("Payload/Demo.app/Demo"),image(0))
            self.seen_clean=True
            return private_process.run(binary,args,env,timeout,root,checkpoint)
        if args[0]=="download":
            archive(Path(args[args.index("--output")+1]),version="9.9" if self.bad_version else "1.2.3")
            if self.mutate_cn:
                account=next(Path(env["HOME"]).glob(".ipatool/*/account.json"))
                value=json.loads(account.read_text());value["store"]="143441";account.write_text(json.dumps(value))
            return subprocess.CompletedProcess([],0,"IPA_LAB_VERSION:123456789:1.2.3\n","")
        if args[0]=="decrypt":
            candidate=Path(args[args.index("--output")+1]);archive(candidate,0,version="9.9" if self.bad_version else "1.2.3")
            report=dict(schema="unfairplay-decryption-v2",complete=True,plaintext_verified=True,
                encrypted_image_count=1,decrypted_page_count=1,account_data=dict(stripped=True),
                output=dict(sha256=digest(candidate)),images=[dict(member="Payload/Demo.app/Demo",slice_offset=0,
                cpu_type=0x0100000C,cpu_subtype=0,pages=1,cryptoff=4096,cryptsize=4096,cryptid_before=1,cryptid_after=0,
                exact_mutation_scope=True,plaintext_validation="code-directory-pre-encryption-hashes",
                pre_encryption_code_directories=[] if self.bad_proof else [dict(slot_count=1,matched_slots=1)])])
            Path(args[args.index("--report")+1]).write_text(json.dumps(report))
        return subprocess.CompletedProcess([],0,"","")

    def export(self,checkpoint=None):
        def stage(name):
            self.stages.append(name)
            if checkpoint:checkpoint(name)
        # The only host substitution is a unit-test platform value; CI flags remain honest.
        with patch.object(context.platform,"system",return_value="Darwin"),patch.object(context.platform,"machine",return_value="arm64"),              patch.object(worker,"check_app",return_value=dict(bundleId="example.synthetic",fileSizeBytes=20000)):
            return worker.export_task(self.task,self.values,self.root/"out",self.env,stage,self.loader,self.execute)

    def make_cn(self):
        self.task.update(profile="cn",request_id="cn_"+"b"*32);self.values=cn_values()

    def test_default_actual_zip_audit_and_age_with_source_bound_receipt(self):
        receipt=self.export();out=self.root/"out"
        self.assertTrue(self.seen_clean);self.assertEqual(receipt["schema"],"circleci-private-delivery-v1")
        self.assertEqual(receipt["run_id"],self.task["run_id"]);self.assertEqual(receipt["source_commit"],self.task["source_sha"])
        self.assertEqual(receipt["encrypted_images"],1);self.assertEqual(receipt["decrypted_pages"],1)
        self.assertEqual(set(x.name for x in out.iterdir()),{"package.ipa.age","receipt.json"})
        self.assertTrue((out/"package.ipa.age").read_bytes().startswith(b"age-encryption.org/v1\n"))
        for name,args,env in self.calls:
            self.assertEqual("APPLEPACKAGE_PASSWORD" in env,args[0]=="login")
            self.assertFalse(any(k.startswith("FAIRPLAY_") or k.startswith("GITHUB_") or k.endswith("_TOKEN") for k in env))
        self.assertEqual((out/"receipt.json").stat().st_mode&0o777,0o600)

    def test_cn_saved_session_never_password_login_or_foreign_model(self):
        self.make_cn();receipt=self.export()
        self.assertEqual(receipt["account_profile"],"cn");self.assertTrue(self.seen_clean)
        commands=[args[0] for _,args,_ in self.calls]
        self.assertIn("resume-cn",commands);self.assertNotIn("login",commands)
        self.assertFalse(any("APPLEPACKAGE_PASSWORD" in env for _,_,env in self.calls))
        for _,_,env in self.calls:self.assertFalse(Path(env["HOME"]).exists())

    def test_exact_historical_version_binding(self):
        self.task["version"]="123456789";receipt=self.export()
        self.assertEqual(receipt["external_version_id"],"123456789")
        self.assertEqual(receipt["resolved_version"],"1.2.3")
        self.assertTrue(any(env.get("LAB_REQUESTED_VERSION")=="123456789" for _,args,env in self.calls if args[0]=="download"))

    def test_wrong_archive_version_fails_before_encrypt(self):
        self.task["version"]="1.2.3";self.bad_version=True
        with self.assertRaises(ValueError):self.export()
        self.assertFalse(self.seen_clean);self.assertFalse((self.root/"out").exists())

    def test_flag_only_or_missing_plaintext_hashes_never_encrypt(self):
        self.bad_proof=True
        with self.assertRaisesRegex(ExportError,"missing_plaintext_hashes"):self.export()
        self.assertFalse(self.seen_clean);self.assertFalse((self.root/"out").exists())

    def test_cn_changed_account_after_download_stops_before_decryption(self):
        self.make_cn();self.mutate_cn=True
        with self.assertRaises(ValueError):self.export()
        self.assertFalse(any(args[0]=="decrypt" for _,args,_ in self.calls));self.assertFalse((self.root/"out").exists())

    def test_cn_checkpoint_guid_or_foreign_credentials_rejected_before_native(self):
        self.make_cn()
        for key,value in (("APPLE_CN_GUID","112233445566"),("APPLE_PASSWORD","forbidden")):
            previous=dict(self.values);self.values[key]=value
            with self.assertRaises(ValueError):self.export()
            self.values=previous
        self.assertEqual(self.calls,[])

    def test_runtime_digest_mismatch_stops_before_account_access(self):
        self.runtime_bad=True
        with self.assertRaisesRegex(ValueError,"runtime_fetch_proof"):self.export()
        self.assertEqual(self.calls,[])

    def test_cancel_at_finalization_retains_no_output(self):
        def stop(stage):
            if stage=="finalizing_ciphertext":raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):self.export(stop)
        self.assertFalse((self.root/"out").exists())

    def test_cancel_at_ready_removes_just_created_output(self):
        def stop(stage):
            if stage=="artifact_ready":raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):self.export(stop)
        self.assertFalse((self.root/"out").exists())

    def test_task_rejects_wrong_source_run_worker_owner_profile_and_github_spoof(self):
        for key,value in (("CIRCLE_SHA1","d"*40),("RUNTIME_RUN_ID",self.task["worker_job_id"]),
            ("CIRCLE_WORKFLOW_JOB_ID",self.task["run_id"]),("CIRCLE_PROJECT_USERNAME","other"),
            ("GITHUB_ACTIONS","true")):
            with self.assertRaisesRegex(ValueError,"task_circleci_context"):
                context.validate(self.task,dict(self.env,**{key:value}),host=("Darwin","arm64"))
        with self.assertRaisesRegex(ValueError,"task_arm_macos_required"):
            context.validate(self.task,self.env,host=("Linux","aarch64"))
        for changed in (dict(self.task,profile="cn"),dict(self.task,recipient="age1"+"q"*58),
            dict(self.task,deadline=int(time.time())-1)):
            with self.assertRaises(ValueError):context.validate(changed,self.env,host=("Darwin","arm64"))

    def test_private_process_cancellation_kills_child_process(self):
        marker=self.root/"child.pid";env=context.minimal_env(self.env,self.root)
        def stop():
            if marker.exists():raise InterruptedError("cancelled")
        code="import os,time,pathlib;pathlib.Path("+repr(str(marker))+").write_text(str(os.getpid()));time.sleep(60)"
        with self.assertRaises(InterruptedError):
            private_process.run(sys.executable,["-c",code],env,10,self.root,stop)
        pid=int(marker.read_text())
        with self.assertRaises(ProcessLookupError):os.kill(pid,0)

    def test_private_process_timeout_and_sensitive_environment(self):
        env=context.minimal_env(self.env,self.root)
        with self.assertRaisesRegex(ValueError,"timeout"):
            private_process.run(sys.executable,["-c","import time;time.sleep(60)"],env,0.3,self.root)
        with self.assertRaisesRegex(ValueError,"environment"):
            private_process.run(sys.executable,["-c","pass"],dict(env,GH_TOKEN="synthetic"),1,self.root)

if __name__=="__main__":unittest.main()
