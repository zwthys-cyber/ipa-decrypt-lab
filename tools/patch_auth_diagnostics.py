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
