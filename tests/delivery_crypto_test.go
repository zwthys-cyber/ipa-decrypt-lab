package main
import(
 "archive/zip"
 "strings"
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
 if run([]string{"scrub","source","target"})==nil{t.Fatal("VPS accepted export scrubbing")}
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

func scrubFixture(t *testing.T, path string, headers []zip.FileHeader) {
 t.Helper()
 f,e:=os.Create(path); if e!=nil {t.Fatal(e)}
 w:=zip.NewWriter(f)
 for _,h:=range headers {
  member,e:=w.CreateHeader(&h); if e!=nil {t.Fatal(e)}
  if _,e=member.Write(bytes.Repeat([]byte("synthetic public fixture"),4096));e!=nil{t.Fatal(e)}
 }
 if e=w.Close();e!=nil{t.Fatal(e)};if e=f.Close();e!=nil{t.Fatal(e)}
}
func TestRawScrubPreservesCompressedDataAndPermissions(t *testing.T) {
 dir:=t.TempDir(); input:=filepath.Join(dir,"source.ipa"); output:=filepath.Join(dir,"clean.ipa")
 main:=zip.FileHeader{Name:"Payload/Test.app/Test",Method:zip.Deflate,Comment:"public fixture"}; main.SetMode(0755)
 names:=[]string{"iTunesMetadata.plist","Payload/Test.app/SC_Info/Test.sinf","loose.SUPF","Nested/license.supp"}
 headers:=[]zip.FileHeader{main}
 for _,name:=range names {headers=append(headers,zip.FileHeader{Name:name,Method:zip.Deflate})}
 scrubFixture(t,input,headers)
 t.Setenv("GITHUB_ACTIONS","true")
 if e:=run([]string{"scrub",input,output});e!=nil{t.Fatal(e)}
 before,e:=zip.OpenReader(input);if e!=nil{t.Fatal(e)};defer before.Close()
 after,e:=zip.OpenReader(output);if e!=nil{t.Fatal(e)};defer after.Close()
 if len(after.File)!=1 || after.File[0].Name!=main.Name {t.Fatal("retained account members")}
 a,_:=before.File[0].OpenRaw();b,_:=after.File[0].OpenRaw();rawA,e:=io.ReadAll(a);if e!=nil{t.Fatal(e)};rawB,e:=io.ReadAll(b);if e!=nil{t.Fatal(e)}
 if !bytes.Equal(rawA,rawB){t.Fatal("recompressed or changed retained bytes")}
 if before.File[0].Mode()!=after.File[0].Mode() || before.File[0].CRC32!=after.File[0].CRC32 {t.Fatal("changed metadata or checksum")}
 reader,e:=after.File[0].Open();if e!=nil{t.Fatal(e)};_,e=io.Copy(io.Discard,reader);reader.Close();if e!=nil{t.Fatal("output CRC failure")}
 info,_:=os.Stat(output);if info.Mode().Perm()!=0600{t.Fatal("unsafe permissions")}
 original,_:=os.ReadFile(output)
 if e=run([]string{"scrub",input,output});e==nil{t.Fatal("overwrote existing output")}
 got,_:=os.ReadFile(output);if !bytes.Equal(original,got){t.Fatal("modified existing output")}
 files,_:=filepath.Glob(filepath.Join(dir,".delivery-scrub-*"));if len(files)!=0{t.Fatal("retained scratch")}
}
func TestRawScrubRejectsUnsafeArchivesAndOutputLinks(t *testing.T) {
 cases:=[][]zip.FileHeader{
  {{Name:"../escape",Method:zip.Store}},
  {{Name:"/absolute",Method:zip.Store}},
  {{Name:"Payload\\bad",Method:zip.Store}},
  {{Name:"same",Method:zip.Store},{Name:"same",Method:zip.Store}},
 }
 link:=zip.FileHeader{Name:"link",Method:zip.Store};link.SetMode(os.ModeSymlink|0777);cases=append(cases,[]zip.FileHeader{link})
 for i,headers:=range cases {t.Run(strings.Repeat("x",i+1),func(t *testing.T){
  dir:=t.TempDir();input:=filepath.Join(dir,"source");output:=filepath.Join(dir,"output")
  scrubFixture(t,input,headers)
  if scrubIPA(input,output)==nil{t.Fatal("accepted unsafe archive")}
  if _,e:=os.Stat(output);!os.IsNotExist(e){t.Fatal("published rejected output")}
 })}
 dir:=t.TempDir(); input:=filepath.Join(dir,"input"); output:=filepath.Join(dir,"output"); destination:=filepath.Join(dir,"existing")
 scrubFixture(t,input,[]zip.FileHeader{{Name:"Payload/app",Method:zip.Store}})
 os.WriteFile(destination,[]byte("untouched"),0600);os.Symlink(destination,output)
 if scrubIPA(input,output)==nil{t.Fatal("accepted output symlink")}
 got,_:=os.ReadFile(destination);if string(got)!="untouched"{t.Fatal("modified symlink target")}
}
func TestScrubWriterEnforcesArchiveBudget(t *testing.T) {
 var output bytes.Buffer
 writer:=&scrubWriter{output:&output,remaining:3}
 if n,e:=writer.Write([]byte("ok"));n!=2||e!=nil{t.Fatal("valid write failed")}
 if _,e:=writer.Write([]byte("no"));e==nil{t.Fatal("exceeded budget")}
 if output.String()!="ok"{t.Fatal("wrote over budget")}
}
