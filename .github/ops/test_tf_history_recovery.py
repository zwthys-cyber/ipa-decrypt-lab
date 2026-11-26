"""Synthetic historical recovery tests; no Secrets, VPS or network."""
from contextlib import closing
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))
from testflight_state import connect,claim
spec=importlib.util.spec_from_file_location("history",Path(__file__).with_name("tf_history_recovery.py"))
history=importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)

class HistoryRecoveryTests(unittest.TestCase):
    def test_live_source_receipt_rejects_unknown_and_changed_state(self):
        # Same closed receipt shape as the source audit, using synthetic data only.
        value={"acceptance_candidates":0,"acceptance_ledger_present":False,
            "acceptance_ledger_valid":False,"acceptance_rows":0,"health_recent":True,
            "known_acceptance_confirmed":False,"private_return_rows":1,"private_return_unknown":0,
            "schema":"ipa-tf-source-audit-v1","service_idle_observed":True,
            "session_ciphertext_present":True,"session_matches_promoted_ciphertext":True,
            "stage":"complete","status":"source_inventory_observed","tf_tasks_total":1,
            "tf_tasks_unfinished":0,"unresolved_acceptance_rows":0}
        history.audit_valid(value)
        for key,bad in (("session_matches_promoted_ciphertext",False),("private_return_unknown",1),
                        ("tf_tasks_unfinished",1),("acceptance_candidates",1),
                        ("acceptance_ledger_present",True),("health_recent",False),
                        ("service_idle_observed",False),("tf_tasks_total",2),
                        ("acceptance_rows",False)):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    history.audit_valid(dict(value,**{key:bad}))
        with self.assertRaises(ValueError):
            history.audit_valid(dict(value,private_account="never accepted"))

    def test_failed_acceptance_is_evidence_not_relabelled_success(self):
        run,source,job,conclusion,schema,status=history.HISTORY[0]
        value={"id":run,"head_sha":source,"run_attempt":1,"head_branch":"main",
            "status":"completed","conclusion":"failure","path":".github/workflows/testflight-virtual.yml"}
        history.run_valid(value,run,source,"failure",value["path"])
        with self.assertRaises(ValueError):
            history.run_valid(dict(value,conclusion="success"),run,source,"failure",value["path"])
        receipt={"schema":schema,"status":status,"run_id":str(run),"source_commit":source,
            "acceptance_attempted":True,"post_response_confirmed":True,"invitation_accepted":False}
        history.history_valid(0,[receipt])
        for changed in (dict(receipt,post_response_confirmed=False),
                        dict(receipt,source_commit="a"*40),
                        dict(receipt,invitation_accepted=True)):
            with self.assertRaises(ValueError):
                history.history_valid(0,[changed])

    def test_read_only_resolution_cannot_hide_another_acceptance(self):
        run,source,job,conclusion,schema,status=history.HISTORY[1]
        receipt={"status":status,"run_id":str(run),"source_commit":source,
            "acceptance_attempted":False,"invitation_accepted":True}
        history.history_valid(1,[receipt])
        for values in ([],[receipt,receipt],
                       [receipt,dict(receipt,status="other",acceptance_attempted=True)]):
            with self.assertRaises(ValueError):
                history.history_valid(1,values)

    def test_historical_packet_checks_origin_and_never_becomes_permit(self):
        cipher=b"age-encryption.org/v1\nsynthetic"
        packet={"schema":"tf-invite-intent-packet-v1","worker_run":"42692803345",
            "source_commit":history.HISTORY[0][1],"nonce":"a"*32,"expires":200,
            "account_binding":"b"*64,"record_path":history.INTENT_PATH,
            "ciphertext_b64":base64.b64encode(cipher).decode(),
            "cipher_sha256":hashlib.sha256(cipher).hexdigest()}
        payload={key:packet[key] for key in ("worker_run","source_commit","nonce","expires","account_binding")}
        payload.update(schema="tf-invite-intent-v1",issued_at=100,app_binding="c"*64,
            invite="yoNuHexZ",origin_run="42650873653",
            origin_source="19244adbe73f71156a91a5c1cb20965925928054")
        history.packet_valid(packet,payload)
        for changed in (dict(payload,invite="anotherInvite"),dict(payload,origin_source="d"*40),
                        dict(payload,nonce="e"*32),dict(payload,expires=201)):
            with self.assertRaises(ValueError):
                history.packet_valid(packet,changed)

    def test_candidate_preserves_confirmed_history_and_denies_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            path=history.candidate(root)
            self.assertEqual(path.stat().st_mode&0o077,0)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("PRAGMA quick_check").fetchall(),[("ok",)])
                self.assertEqual(db.execute("SELECT count(*) FROM invitations").fetchone(),(1,))
                self.assertEqual(db.execute("SELECT value FROM recovery_provenance WHERE name='production_installed'").fetchone(),("false",))
            with closing(connect(path.parent)) as db:
                result=claim(db,{"invite":"yoNuHexZ","request_id":"tf_"+"a"*32,
                    "run_id":"123","source_commit":"b"*40},now=9999999999)
                self.assertFalse(result["permitted"])
                self.assertEqual(result["previous_state"],"membership_verified")
            self.assertFalse((root/"state.sqlite3").exists())
            self.assertFalse((root/"testflight/session.age").exists())

if __name__=="__main__":
    unittest.main()
