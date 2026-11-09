package main
import("bytes";"crypto/rand";"encoding/base64";"testing";"golang.org/x/crypto/nacl/box")
func TestRepositorySealedPriorProfile(t *testing.T){
 pub,priv,e:=box.GenerateKey(rand.Reader);if e!=nil{t.Fatal(e)}
 raw:=[]byte(`{"schema":"cn-arm-prior-profile-v1","account":"synthetic private fixture"}`)
 sealed,e:=seal(raw,pub);if e!=nil{t.Fatal(e)}
 plain,ok:=box.OpenAnonymous(nil,sealed,pub,priv);if !ok{t.Fatal("sealed session unavailable")}
 decoded,e:=base64.StdEncoding.Strict().DecodeString(string(plain));if e!=nil||!bytes.Equal(decoded,raw){t.Fatal("session mismatch")}
 other,otherPriv,_:=box.GenerateKey(rand.Reader)
 if _,ok=box.OpenAnonymous(nil,sealed,other,otherPriv);ok{t.Fatal("accepted wrong recipient")}
 if _,e=seal(make([]byte,32769),pub);e==nil{t.Fatal("accepted oversize")}
 if _,e=seal(nil,pub);e==nil{t.Fatal("accepted empty")}
}
