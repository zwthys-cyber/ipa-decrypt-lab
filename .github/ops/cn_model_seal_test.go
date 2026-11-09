package main
import (
 "bytes"
 "crypto/rand"
 "encoding/base64"
 "testing"
 "golang.org/x/crypto/nacl/box"
)
func TestSealedSecretRoundTripAndTamperRejection(t *testing.T){
 pub,priv,err:=box.GenerateKey(rand.Reader);if err!=nil{t.Fatal("key generation")}
 raw:=[]byte("PRIVATE_SYNTHETIC_MODEL")
 cipher,err:=sealModel(raw,base64.StdEncoding.EncodeToString(pub[:]));if err!=nil{t.Fatal("sealing")}
 clearText,ok:=box.OpenAnonymous(nil,cipher,pub,priv)
 if !ok || string(clearText)!=base64.StdEncoding.EncodeToString(raw){t.Fatal("secret plaintext mismatch")}
 if bytes.Contains(cipher,raw){t.Fatal("unsealed content")}
 cipher[len(cipher)-1]^=1
 if _,ok:=box.OpenAnonymous(nil,cipher,pub,priv);ok{t.Fatal("tampered ciphertext accepted")}
}
func TestSealingRejectsInvalidInputs(t *testing.T){
 for _,raw:=range [][]byte{nil,make([]byte,modelLimit+1)}{if _,err:=sealModel(raw,publicKey);err==nil{t.Fatal("invalid size accepted")}}
 if _,err:=sealModel([]byte("private"),"invalid");err==nil{t.Fatal("invalid key accepted")}
}

func TestFixedSecretPurpose(t *testing.T) {
 for _, tc:=range []struct{ args []string; schema, secret string; valid bool }{
  {[]string{"seal","private.bin"},"ipa-lab-github-sealed-model-v1","FAIRPLAY_CN_MODEL_B64",true},
  {[]string{"seal","private.bin","state"},"ipa-lab-github-sealed-state-v1","FAIRPLAY_CN_STATE_B64",true},
  {[]string{"seal","private.bin","guid"},"ipa-lab-github-sealed-cn-guid-v1","APPLE_CN_GUID",true},
  {[]string{"seal","private.bin","OTHER"},"","",false},
  {[]string{"seal"},"","",false},
 } {
  schema,secret,err:=target(tc.args)
  if (err==nil)!=tc.valid || schema!=tc.schema || secret!=tc.secret { t.Fatal("invalid purpose binding") }
 }
}

func TestGUIDSecretHasRawValidatedText(t *testing.T) {
 pub,priv,err:=box.GenerateKey(rand.Reader);if err!=nil { t.Fatal("key generation") }
 raw:=[]byte("001122AABBCC");cipher,err:=sealGUID(raw,base64.StdEncoding.EncodeToString(pub[:]))
 if err!=nil { t.Fatal("sealing") };plain,ok:=box.OpenAnonymous(nil,cipher,pub,priv)
 if !ok||!bytes.Equal(plain,raw) { t.Fatal("raw guid secret mismatch") }
 for _,invalid:=range [][]byte{nil,[]byte("001122aabbcc"),[]byte("001122AABBCX"),[]byte("00:11:22:33:44:55")} {
  if _,err:=sealGUID(invalid,publicKey);err==nil { t.Fatal("invalid guid accepted") }
 }
}
