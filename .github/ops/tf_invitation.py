"""Offline invitation plans and durable at-most-once acceptance intents.

No authentication, HTTP client or live acceptance is implemented here. A future
worker must sign each canonical request using a verified TF session, inspect the
invitation, and persist acceptance intent before sending the POST. A 2xx alone
is not proof of tester membership or beta download.
"""
from dataclasses import dataclass
import hashlib
import re
import sqlite3

_CODE = re.compile(r"[A-Za-z0-9_-]{6,80}")
_LINK = re.compile(r"https://testflight[.]apple[.]com/join/([A-Za-z0-9_-]{6,80})")
_ACCOUNT = re.compile(r"[A-Za-z0-9_-]{1,128}")

def invite_code(link):
    if type(link) is not str or len(link)>160:
        raise ValueError("tf_invitation_invalid")
    match=_LINK.fullmatch(link)
    if match is None:
        raise ValueError("tf_invitation_invalid")
    return match.group(1)

@dataclass(frozen=True)
class RequestPlan:
    method: str
    url: str

def request_plan(account_id, code, *, accept=False):
    if type(account_id) is not str or _ACCOUNT.fullmatch(account_id) is None:
        raise ValueError("tf_account_invalid")
    if type(code) is not str or _CODE.fullmatch(code) is None or type(accept) is not bool:
        raise ValueError("tf_invitation_invalid")
    base="https://testflight.apple.com/v3/accounts/"+account_id+"/ru/"+code
    return RequestPlan("POST" if accept else "GET", base+("/accept" if accept else ""))

def response_category(status):
    if type(status) is not int or not 100<=status<=599:
        raise ValueError("tf_response_invalid")
    if status in (401,403):return "authentication_required"
    if status==404:return "invitation_unavailable"
    if status==429:return "rate_limited"
    if 200<=status<300:return "response_requires_verification"
    return "request_failed"

class InvitationJournal:
    """Use a worker-owned private SQLite connection; never store TF credentials.

    The account token is hashed to keep raw account identifiers out of the
    journal. An intent survives crashes/timeouts, and blocks automatic POST
    repeats even when the caller uses a different job ID.
    """
    def __init__(self, connection):
        self.connection=connection
        connection.execute("""CREATE TABLE IF NOT EXISTS tf_invitation_intents (
            account_binding TEXT NOT NULL, invite TEXT NOT NULL,
            request_binding TEXT NOT NULL, state TEXT NOT NULL,
            PRIMARY KEY(account_binding, invite))""")
        connection.commit()

    def claim(self, account_id, code, request_binding):
        request_plan(account_id,code,accept=True)
        if type(request_binding) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,128}",request_binding) is None:
            raise ValueError("tf_request_binding_invalid")
        binding=hashlib.sha256(account_id.encode("ascii")).hexdigest()
        try:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO tf_invitation_intents VALUES (?,?,?,?)",
                    (binding,code,request_binding,"acceptance_outcome_unverified"))
        except sqlite3.IntegrityError:
            return False
        return True
