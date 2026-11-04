// Private delivery encryption using the audited age format, not a custom cipher.
package main

import (
 "crypto/rand"
 "encoding/base64"
 "encoding/json"
 "errors"
 "fmt"
 "io"
 "os"
 "path/filepath"
 "filippo.io/age"
 "golang.org/x/crypto/nacl/box"
)

const maxBytes int64 = 1024*1024*1024
const repositoryKey = "smSbVehBpVp8xXXQxSzjJyoZG5UJd+/m26YlP7sEa1g="
const repositoryKeyID = "3380204578043523366"

func source(path string, limit int64) (*os.File, error) {
 s,e:=os.Lstat(path)
 if e!=nil || !s.Mode().IsRegular() || s.Size()<=0 || s.Size()>limit { return nil,errors.New("invalid input") }
 return os.Open(path)
}

// Output appears only after all stream authentication, bounds and close checks pass.
// Link publishes without overwriting an existing output, including a symlink.
func transform(input, output string, decrypt bool, key string) (err error) {
 limit:=maxBytes
 if decrypt { limit+=1024*1024 }
 src,err:=source(input,limit); if err!=nil { return err }; defer src.Close()
 tmp,err:=os.CreateTemp(filepath.Dir(output),".delivery-*"); if err!=nil { return err }
 defer func(){ tmp.Close(); os.Remove(tmp.Name()) }()
 if decrypt {
  identity,e:=age.ParseX25519Identity(key); if e!=nil { return e }
  reader,e:=age.Decrypt(src,identity); if e!=nil { return e }
  n,e:=io.Copy(tmp,io.LimitReader(reader,maxBytes+1))
  if e!=nil || n<=0 || n>maxBytes { return errors.New("decryption rejected") }
 } else {
  recipient,e:=age.ParseX25519Recipient(key); if e!=nil { return e }
  writer,e:=age.Encrypt(tmp,recipient); if e!=nil { return e }
  n,e:=io.Copy(writer,io.LimitReader(src,maxBytes+1))
  if e!=nil || n<=0 || n>maxBytes { return errors.New("encryption rejected") }
  if e=writer.Close(); e!=nil { return e }
 }
 if err=tmp.Sync(); err!=nil { return err }
 if err=tmp.Close(); err!=nil { return err }
 return os.Link(tmp.Name(),output)
}

func sealedIdentity() error {
 identity,err:=age.GenerateX25519Identity(); if err!=nil { return err }
 decoded,err:=base64.StdEncoding.Strict().DecodeString(repositoryKey)
 if err!=nil || len(decoded)!=32 { return errors.New("invalid repository key") }
 var key [32]byte; copy(key[:],decoded)
 private:=[]byte(identity.String()); defer clear(private)
 ciphertext,err:=box.SealAnonymous(nil,private,&key,rand.Reader); if err!=nil { return err }
 return json.NewEncoder(os.Stdout).Encode(map[string]any{
  "schema":"ipa-delivery-sealed-identity-v1",
  "repository":"zwthys-cyber/ipa-decrypt-lab",
  "secret_name":"DELIVERY_AGE_IDENTITY", "key_id":repositoryKeyID,
  "encrypted_value":base64.StdEncoding.EncodeToString(ciphertext),
  "recipient":identity.Recipient().String(),
 })
}
func run(args []string) error {
 if os.Getenv("GITHUB_ACTIONS")!="true" { return errors.New("requires GitHub Actions") }
 if len(args)==1 && args[0]=="keygen" { return sealedIdentity() }
 if len(args)==4 && args[0]=="encrypt" { return transform(args[1],args[2],false,args[3]) }
 if len(args)==3 && args[0]=="decrypt" { return transform(args[1],args[2],true,os.Getenv("DELIVERY_AGE_IDENTITY")) }
 return errors.New("invalid invocation")
}
func main(){
 if run(os.Args[1:])!=nil { fmt.Fprintln(os.Stderr,"private_delivery_crypto_failed"); os.Exit(2) }
}
