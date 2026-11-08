// Private delivery encryption using the audited age format, not a custom cipher.
package main

import (
 "archive/zip"
 "strings"
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

const maxBytes int64 = 2000000000
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
 if decrypt { limit+=4*1024*1024 }
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


// Copy existing compressed members; verify_output still checks every output CRC,
// Mach-O inventory and plaintext proof before encryption or publication.
type scrubWriter struct { output io.Writer; remaining int64 }
func (w *scrubWriter) Write(p []byte) (int,error) {
 if int64(len(p))>w.remaining { return 0,errors.New("archive size limit") }
 n,e:=w.output.Write(p); w.remaining-=int64(n); return n,e
}
func privateMember(name string) bool {
 parts:=strings.Split(strings.ToLower(strings.TrimSuffix(name,"/")),"/")
 for _,part:=range parts { if part=="sc_info" { return true } }
 leaf:=parts[len(parts)-1]
 return leaf=="itunesmetadata.plist" || strings.HasSuffix(leaf,".sinf") || strings.HasSuffix(leaf,".supf") || strings.HasSuffix(leaf,".supp")
}
func scrubIPA(input,output string) error {
 src,e:=source(input,maxBytes); if e!=nil { return e }; defer src.Close()
 info,e:=src.Stat(); if e!=nil { return e }
 archive,e:=zip.NewReader(src,info.Size()); if e!=nil { return e }
 if len(archive.File)==0 || len(archive.File)>32768 { return errors.New("archive entry limit") }
 names:=make(map[string]bool); var expanded uint64; kept:=0
 for _,f:=range archive.File {
  name:=f.Name
  if name=="" || strings.HasPrefix(name,"/") || strings.ContainsAny(name,"\\\x00") || names[name] || f.Mode()&os.ModeSymlink!=0 || f.Flags&1!=0 || (f.Method!=zip.Store && f.Method!=zip.Deflate) { return errors.New("invalid archive member") }
  for _,part:=range strings.Split(strings.TrimSuffix(name,"/"),"/") {
   if part=="" || part=="." || part==".." { return errors.New("unsafe archive path") }
  }
  names[name]=true
  if f.UncompressedSize64>uint64(maxBytes) || f.CompressedSize64>uint64(info.Size()) || f.UncompressedSize64>uint64(3*maxBytes)-expanded { return errors.New("archive expansion limit") }
  expanded+=f.UncompressedSize64
  if !privateMember(name) { kept++ }
 }
 if kept==0 { return errors.New("empty scrubbed archive") }
 tmp,e:=os.CreateTemp(filepath.Dir(output),".delivery-scrub-*"); if e!=nil { return e }
 defer func(){ tmp.Close(); os.Remove(tmp.Name()) }()
 writer:=zip.NewWriter(&scrubWriter{output:tmp,remaining:maxBytes})
 for _,f:=range archive.File {
  if privateMember(f.Name) { continue }
  if e=writer.Copy(f); e!=nil { return e }
 }
 if e=writer.Close(); e!=nil { return e }
 if e=tmp.Sync(); e!=nil { return e }
 if e=tmp.Close(); e!=nil { return e }
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
 if os.Getenv("GITHUB_ACTIONS")!="true" {
  if os.Getenv("LAB_RUNTIME")=="vps" && len(args)==3 && args[0]=="decrypt" {
   return transform(args[1],args[2],true,os.Getenv("DELIVERY_AGE_IDENTITY"))
  }
  return errors.New("requires GitHub Actions")
 }
 if len(args)==3 && args[0]=="scrub" { return scrubIPA(args[1],args[2]) }
 if len(args)==1 && args[0]=="keygen" { return sealedIdentity() }
 if len(args)==4 && args[0]=="encrypt" { return transform(args[1],args[2],false,args[3]) }
 if len(args)==3 && args[0]=="decrypt" { return transform(args[1],args[2],true,os.Getenv("DELIVERY_AGE_IDENTITY")) }
 return errors.New("invalid invocation")
}
func main(){
 if run(os.Args[1:])!=nil { fmt.Fprintln(os.Stderr,"private_delivery_crypto_failed"); os.Exit(2) }
}
