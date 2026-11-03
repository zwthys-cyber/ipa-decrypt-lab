"""Patch the pinned dependency's ambiguous bad-login => definite-2FA mapping."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
path = root/"pkg/appstore/appstore_login.go"
old = '''if authCode == "" {
			err = ErrAuthCodeRequired
		} else {
			err = errors.New("apple did not complete verification; try a fresh 2FA code")
		}'''
new = '''// A generic bad-login response is not proof of a second-factor challenge.
		// Preserve uncertainty and only expose a category and HTTP status.
		err = fmt.Errorf("apple_auth_ambiguous_bad_login (HTTP %d)", res.StatusCode)'''
source = path.read_text()
if source.count(old) != 1:
    raise SystemExit("Pinned authentication source changed; refusing an unverified patch")
path.write_text(source.replace(old, new))
test = root/"pkg/appstore/auth_diagnostic_regression_test.go"
test.write_text('''package appstore

import (
    "errors"
    "strings"
    "testing"
    "github.com/majd/ipatool/v2/pkg/http"
)

func TestGenericBadLoginIsNotDefiniteTwoFactor(t *testing.T) {
    for _, code := range []string{"", "123456"} {
        store := &appstore{}
        response := http.Result[loginResult]{
            StatusCode: 200,
            Data: loginResult{CustomerMessage: CustomerMessageBadLogin},
        }
        retry, redirect, err := store.parseLoginResponse(&response, 2, code, "https://example.invalid")
        if retry || redirect != "" || err == nil {
            t.Fatal("generic bad-login must stop with a diagnostic")
        }
        if errors.Is(err, ErrAuthCodeRequired) || !strings.Contains(err.Error(), "apple_auth_ambiguous_bad_login") {
            t.Fatal("generic response must not be labeled a definite 2FA challenge")
        }
    }
}
''')


profile = sys.argv[2] if len(sys.argv) > 2 else "upstream"
if profile not in {"upstream", "plist-compat"}:
    raise SystemExit("unknown authentication profile")
if profile == "plist-compat":
    # Request shape independently compared with pinned AssppWeb 485be0b.
    # Do not change the endpoint, SAP signer, certificate checks or credentials.
    source = path.read_text()
    replacements = {
        '"Content-Type": "application/x-www-form-urlencoded"': '"Content-Type": "application/x-apple-plist"',
        '"attempt":  strconv.Itoa(attempt)': '"attempt":  strconv.Itoa(compatibilityWireAttempt(authCode))',
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise SystemExit("pinned request template changed; refusing compatibility patch")
        source = source.replace(before, after)
    source += '''
func compatibilityWireAttempt(authCode string) int {
    if authCode == "" {
        return 4
    }
    return 2
}
'''
    path.write_text(source)
    extra = root/"pkg/appstore/auth_wire_compatibility_test.go"
    extra.write_text('''package appstore
import (
    "testing"
    "github.com/majd/ipatool/v2/pkg/http"
)
func TestPlistCompatibilityRequest(t *testing.T) {
    for _, item := range []struct{code, attempt, password string}{
        {"", "4", "synthetic-password"},
        {"123456", "2", "synthetic-password123456"},
    } {
        store := &appstore{}
        request := store.loginRequest("synthetic@example.invalid", "synthetic-password",
            item.code, "synthetic-guid", "https://auth.itunes.apple.com/auth/v1/native/fast/", 1, nil)
        if request.Headers["Content-Type"] != "application/x-apple-plist" {
            t.Fatal("incorrect request content type")
        }
        payload, ok := request.Payload.(*http.XMLPayload)
        if !ok || payload.Content["attempt"] != item.attempt || payload.Content["password"] != item.password {
            t.Fatal("incorrect request attempt/password construction")
        }
        if request.URL != "https://auth.itunes.apple.com/auth/v1/native/fast/" {
            t.Fatal("compatibility profile must not replace the configured endpoint")
        }
    }
}
''')
