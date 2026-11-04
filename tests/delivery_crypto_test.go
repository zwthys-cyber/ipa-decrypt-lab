package main
import(
 "bytes"
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
