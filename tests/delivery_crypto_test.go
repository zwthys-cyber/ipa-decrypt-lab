package main
import(
 "bytes"
 "crypto/sha256"
 "io"
 "os"
 "path/filepath"
 "testing"
 "filippo.io/age"
)
func TestAuthenticatedDelivery(t *testing.T){
 dir:=t.TempDir()
 input:=filepath.Join(dir,"input.ipa"); encrypted:=filepath.Join(dir,"input.age")
 plain:=bytes.Repeat([]byte("synthetic-private-ipa"),10000)
 if e:=os.WriteFile(input,plain,0600);e!=nil{t.Fatal(e)}
 key,e:=age.GenerateX25519Identity();if e!=nil{t.Fatal(e)}
 if e=transform(input,encrypted,false,key.Recipient().String());e!=nil{t.Fatal(e)}
 output:=filepath.Join(dir,"output.ipa")
 if e=transform(encrypted,output,true,key.String());e!=nil{t.Fatal(e)}
 got,e:=os.ReadFile(output);if e!=nil||!bytes.Equal(got,plain){t.Fatal("round trip mismatch")}
 info,_:=os.Stat(output);if info.Mode().Perm()!=0600{t.Fatal("unsafe output mode")}
 if e=transform(encrypted,output,true,key.String());e==nil{t.Fatal("overwrote existing output")}
 raw,_:=os.ReadFile(encrypted)
 other,_:=age.GenerateX25519Identity()
 cases:=[]struct{name string; data []byte; identity string}{
  {"wrong-key",raw,other.String()},
  {"truncated",raw[:len(raw)-1],key.String()},
  {"header-only",raw[:100],key.String()},
  {"empty",nil,key.String()},
 }
 changed:=append([]byte{},raw...);changed[len(changed)-20]^=1
 cases=append(cases,struct{name string;data []byte;identity string}{"tampered",changed,key.String()})
 for _,c:=range cases{t.Run(c.name,func(t *testing.T){
  f:=filepath.Join(dir,c.name+".age");out:=filepath.Join(dir,c.name+".ipa")
  os.WriteFile(f,c.data,0600)
  if transform(f,out,true,c.identity)==nil{t.Fatal("accepted unauthenticated data")}
  if _,e:=os.Stat(out);!os.IsNotExist(e){t.Fatal("published partial plaintext")}
 })}
 files,_:=filepath.Glob(filepath.Join(dir,".delivery-*"));if len(files)!=0{t.Fatal("temporary plaintext retained")}
}
func TestRejectSymlinksAndOversize(t *testing.T){
 dir:=t.TempDir()
 original:=filepath.Join(dir,"original")
 os.WriteFile(original,[]byte("fixture"),0600)
 link:=filepath.Join(dir,"link");os.Symlink(original,link)
 if f,e:=source(link,100);e==nil{f.Close();t.Fatal("accepted symlink")}
 if f,e:=source(original,1);e==nil{f.Close();t.Fatal("accepted oversized input")}
}

func TestVPSRuntimeOnlyDecrypts(t *testing.T){
 t.Setenv("GITHUB_ACTIONS","")
 t.Setenv("LAB_RUNTIME","vps")
 if run([]string{"keygen"})==nil{t.Fatal("VPS generated repository identity")}
 dir:=t.TempDir()
 input:=filepath.Join(dir,"input")
 encrypted:=filepath.Join(dir,"ciphertext")
 output:=filepath.Join(dir,"output")
 plain:=[]byte("synthetic VPS delivery")
 if e:=os.WriteFile(input,plain,0600);e!=nil{t.Fatal(e)}
 identity,e:=age.GenerateX25519Identity();if e!=nil{t.Fatal(e)}
 if run([]string{"encrypt",input,encrypted,identity.Recipient().String()})==nil{t.Fatal("VPS accepted export encryption mode")}
 if e=transform(input,encrypted,false,identity.Recipient().String());e!=nil{t.Fatal(e)}
 t.Setenv("DELIVERY_AGE_IDENTITY",identity.String())
 if e=run([]string{"decrypt",encrypted,output});e!=nil{t.Fatal(e)}
 got,e:=os.ReadFile(output);if e!=nil||!bytes.Equal(got,plain){t.Fatal("VPS decrypt mismatch")}
 t.Setenv("LAB_RUNTIME","")
 if run([]string{"decrypt",encrypted,filepath.Join(dir,"forbidden")})==nil{t.Fatal("unconfigured runtime accepted")}
}

func TestLargeCapacityRoundTrip(t *testing.T) {
 if os.Getenv("LAB_LARGE_CAPACITY_TEST")!="1" { t.Skip("large stream test is enabled in the release workflow") }
 dir:=t.TempDir()
 input:=filepath.Join(dir,"boundary.ipa"); encrypted:=filepath.Join(dir,"boundary.age"); output:=filepath.Join(dir,"restored.ipa")
 f,e:=os.OpenFile(input,os.O_CREATE|os.O_RDWR,0600); if e!=nil {t.Fatal(e)}
 if e=f.Truncate(maxBytes); e!=nil {t.Fatal(e)}
 if _,e=f.WriteAt([]byte("boundary-marker"),maxBytes-15); e!=nil {t.Fatal(e)}
 f.Close()
 key,e:=age.GenerateX25519Identity(); if e!=nil {t.Fatal(e)}
 if e=transform(input,encrypted,false,key.Recipient().String()); e!=nil {t.Fatal(e)}
 if e=transform(encrypted,output,true,key.String()); e!=nil {t.Fatal(e)}
 hash:=func(path string) []byte { f,e:=os.Open(path); if e!=nil {t.Fatal(e)}; defer f.Close(); h:=sha256.New(); n,e:=io.Copy(h,f); if e!=nil || n!=maxBytes {t.Fatal("size mismatch")}; return h.Sum(nil) }
 if !bytes.Equal(hash(input),hash(output)) {t.Fatal("large stream digest mismatch")}
 if e=os.Truncate(input,maxBytes+1); e!=nil {t.Fatal(e)}
 if e=transform(input,filepath.Join(dir,"forbidden.age"),false,key.Recipient().String()); e==nil {t.Fatal("accepted oversized plaintext")}
}
