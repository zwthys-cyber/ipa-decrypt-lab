"""Standard age envelopes bound to one approved CircleCI job; never log credential values."""
import json
import os
from pathlib import Path
import re
import subprocess
import time

BRANCH = "upgrade/managed-runtime-v0.2"
REPO = "zwthys-cyber/ipa-decrypt-lab"
UUID = r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"
MAX_PLAIN = 196608
MAX_CIPHER = 262144
FIELDS = {"schema","job_id","run_id","worker_job_id","source_sha","recipient","nonce","expires_at","profile"}
PROFILES = {
    "synthetic": {"fixture"},
    "default_catalog": {"APPLE_ID","APPLE_PASSWORD"},
    "cn_catalog": {"APPLE_CN_ID","APPLE_CN_GUID","APPLE_CN_SESSION_B64"},
    "default": {"APPLE_ID","APPLE_PASSWORD","FAIRPLAY_MODEL_B64"},
    "cn": {"APPLE_CN_ID","APPLE_CN_GUID","APPLE_CN_SESSION_B64","FAIRPLAY_CN_MODEL_B64","FAIRPLAY_CN_STATE_B64"},
    "tf": {"TF_SAVED_SESSION_B64","FAIRPLAY_CN_MODEL_B64"},
}

def require(value, reason):
    if not value:
        raise ValueError(reason)

def context(value, now=None):
    now = int(time.time()) if now is None else now
    require(type(value) is dict and set(value) == FIELDS and
            value.get("schema") == "circleci-credential-request-v1", "lease_context_schema")
    require(re.fullmatch(r"pilot_[a-f0-9]{32}", value.get("job_id","")) and
            re.fullmatch(UUID,value.get("run_id","")) and re.fullmatch(UUID,value.get("worker_job_id","")) and
            re.fullmatch(r"[a-f0-9]{40}",value.get("source_sha","")) and
            re.fullmatch(r"age1[0-9a-z]{58}",value.get("recipient","")) and
            re.fullmatch(r"[a-f0-9]{32}",value.get("nonce","")), "lease_context_identity")
    require(value.get("profile") in PROFILES and type(value.get("expires_at")) is int and
            now < value["expires_at"] <= now+600, "lease_context_expired")
    return dict(value)

def issuer(env, expected):
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPO and
            env.get("GITHUB_REF") == "refs/heads/"+BRANCH and env.get("GITHUB_SHA") == expected["source_sha"],
            "lease_issuer_context")

def consumer(env, expected):
    require(env.get("CIRCLECI") == "true" and not env.get("GITHUB_ACTIONS") and
            env.get("CIRCLE_BRANCH") == BRANCH and env.get("CIRCLE_SHA1") == expected["source_sha"] and
            env.get("CIRCLE_WORKFLOW_JOB_ID") == expected["worker_job_id"] and
            (env.get("RUNTIME_RUN_ID") or env.get("PROBE_PIPELINE")) == expected["run_id"],
            "lease_consumer_context")

def public_env(env):
    return {key:env[key] for key in ("PATH","HOME","LANG","TMPDIR") if key in env}

def credentials(profile, values):
    require(type(values) is dict and set(values) == PROFILES[profile], "lease_profile_fields")
    require(all(type(v) is str and 0 < len(v.encode()) <= 65536 and "\x00" not in v
                for v in values.values()), "lease_credential_shape")
    return dict(values)

def seal(expected, values, env=None, now=None, execute=subprocess.run):
    env = os.environ if env is None else env
    expected = context(expected, now);issuer(env, expected)
    packet = dict(schema="circleci-credential-envelope-v1",context=expected,
                  credentials=credentials(expected["profile"],values))
    raw = json.dumps(packet,separators=(",",":"),sort_keys=True).encode()
    require(len(raw) <= MAX_PLAIN, "lease_plain_limit")
    result = execute(["age","--encrypt","--recipient",expected["recipient"]],input=raw,
                     capture_output=True,timeout=30,env=public_env(env))
    require(result.returncode == 0 and result.stdout.startswith(b"age-encryption.org/v1\n") and
            0 < len(result.stdout) <= MAX_CIPHER, "lease_encrypt_failed")
    return result.stdout

def open_envelope(cipher, key_file, expected, env=None, now=None, execute=subprocess.run):
    env = os.environ if env is None else env
    expected = context(expected, now);consumer(env, expected)
    require(type(cipher) is bytes and cipher.startswith(b"age-encryption.org/v1\n") and
            0 < len(cipher) <= MAX_CIPHER, "lease_cipher_limit")
    key_file = Path(key_file)
    require(key_file.is_file() and not key_file.is_symlink() and key_file.stat().st_mode & 0o077 == 0,
            "lease_key_permissions")
    result = execute(["age","--decrypt","--identity",str(key_file)],input=cipher,
                     capture_output=True,timeout=30,env=public_env(env))
    require(result.returncode == 0 and 0 < len(result.stdout) <= MAX_PLAIN, "lease_decrypt_failed")
    packet = json.loads(result.stdout)
    require(type(packet) is dict and set(packet) == {"schema","context","credentials"} and
            packet["schema"] == "circleci-credential-envelope-v1" and packet["context"] == expected,
            "lease_packet_binding")
    return credentials(expected["profile"],packet["credentials"])
