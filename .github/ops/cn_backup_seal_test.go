package main
import("bytes";"crypto/rand";"encoding/base64";"testing";"os";"path/filepath";"io";"encoding/json";"golang.org/x/crypto/nacl/box")
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

func TestBackupDestinationAndPrivateFileBoundary(t *testing.T){
 t.Setenv("GITHUB_ACTIONS","true")
 path:=filepath.Join(t.TempDir(),"snapshot.json")
 if os.WriteFile(path,[]byte(`{"schema":"cn-arm-prior-profile-v1","fixture":true}`),0600)!=nil{t.Fatal("fixture")}
 reader,writer,e:=os.Pipe();if e!=nil{t.Fatal("pipe")}
 previous:=os.Stdout;os.Stdout=writer;err:=run(path);os.Stdout=previous;writer.Close();raw,e:=io.ReadAll(reader);reader.Close()
 if err!=nil||e!=nil{t.Fatal("seal invocation")}
 var value map[string]string;if json.Unmarshal(raw,&value)!=nil||len(value)!=5||value["schema"]!="ipa-cn-recovery-backup-secret-v1"||value["secret_name"]!="CN_RECOVERY_BACKUP_B64"||value["repository"]!="zwthys-cyber/ipa-decrypt-lab"{t.Fatal("destination")}
 if os.Chmod(path,0644)!=nil{t.Fatal("permissions")};if run(path)==nil{t.Fatal("accepted public input")}
 if os.Chmod(path,0600)!=nil{t.Fatal("permissions")};link:=path+"-link";if os.Symlink(path,link)!=nil{t.Fatal("symlink")};if run(link)==nil{t.Fatal("accepted symlink")}
 t.Setenv("GITHUB_ACTIONS","false");if run(path)==nil{t.Fatal("accepted non Actions")}
}
