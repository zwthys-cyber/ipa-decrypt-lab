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
