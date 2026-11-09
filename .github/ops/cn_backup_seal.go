package main
import("crypto/rand";"encoding/base64";"encoding/json";"errors";"fmt";"os";"golang.org/x/crypto/nacl/box")
const keyText="smSbVehBpVp8xXXQxSzjJyoZG5UJd+/m26YlP7sEa1g="
const keyID="3380204578043523366"
func seal(raw []byte,key *[32]byte)([]byte,error){
 if len(raw)==0||len(raw)>32768{return nil,errors.New("session size")}
 plain:=[]byte(base64.StdEncoding.EncodeToString(raw));defer clear(plain)
 return box.SealAnonymous(nil,plain,key,rand.Reader)
}
func run(path string)error{
 if os.Getenv("GITHUB_ACTIONS")!="true"{return errors.New("GitHub only")}
 info,e:=os.Lstat(path);if e!=nil||!info.Mode().IsRegular()||info.Mode().Perm()&0077!=0||info.Size()>32768{return errors.New("private session required")}
 raw,e:=os.ReadFile(path);if e!=nil{return e};defer clear(raw)
 keyBytes,e:=base64.StdEncoding.Strict().DecodeString(keyText);if e!=nil||len(keyBytes)!=32{return errors.New("key invalid")}
 var key [32]byte;copy(key[:],keyBytes);cipher,e:=seal(raw,&key);if e!=nil{return e}
 return json.NewEncoder(os.Stdout).Encode(map[string]string{"schema":"ipa-cn-recovery-backup-secret-v1","repository":"zwthys-cyber/ipa-decrypt-lab","secret_name":"CN_RECOVERY_BACKUP_B64","key_id":keyID,"encrypted_value":base64.StdEncoding.EncodeToString(cipher)})
}
func main(){if len(os.Args)!=2||run(os.Args[1])!=nil{fmt.Fprintln(os.Stderr,"private_cn_backup_seal_failed");os.Exit(2)}}
