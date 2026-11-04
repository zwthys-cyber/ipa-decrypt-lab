package main

import (
 "crypto/rand"
 "encoding/base64"
 "encoding/json"
 "fmt"
 "os"
 "golang.org/x/crypto/nacl/box"
)

const publicKey = "smSbVehBpVp8xXXQxSzjJyoZG5UJd+/m26YlP7sEa1g="
const keyID = "3380204578043523366"
const modelLimit = 32768

func sealModel(raw []byte, key string) ([]byte, error) {
 if len(raw)==0 || len(raw)>modelLimit { return nil, fmt.Errorf("invalid model size") }
 decoded, err := base64.StdEncoding.Strict().DecodeString(key)
 if err != nil || len(decoded)!=32 { return nil, fmt.Errorf("invalid public key") }
 var recipient [32]byte
 copy(recipient[:],decoded)
 // GitHub receives a base64 model as the Secret plaintext, sealed to its repository key.
 private := []byte(base64.StdEncoding.EncodeToString(raw))
 defer clear(private)
 return box.SealAnonymous(nil,private,&recipient,rand.Reader)
}

func target(args []string) (string,string,error) {
 if len(args)==2 { return "ipa-lab-github-sealed-model-v1","FAIRPLAY_MODEL_B64",nil }
 if len(args)==3 && args[2]=="state" { return "ipa-lab-github-sealed-state-v1","FAIRPLAY_STATE_B64",nil }
 return "","",fmt.Errorf("invalid purpose")
}

func run() error {
 schema,secret,targetErr:=target(os.Args)
 if targetErr!=nil || os.Getenv("GITHUB_ACTIONS")!="true" { return fmt.Errorf("invalid invocation") }
 info,err:=os.Lstat(os.Args[1])
 if err!=nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077!=0 || info.Size()<=0 || info.Size()>modelLimit {
  return fmt.Errorf("invalid model file")
 }
 raw,err:=os.ReadFile(os.Args[1])
 if err!=nil { return fmt.Errorf("model unavailable") }
 defer clear(raw)
 sealed,err:=sealModel(raw,publicKey)
 if err!=nil { return err }
 return json.NewEncoder(os.Stdout).Encode(map[string]any{
  "schema":schema,
  "repository":"zwthys-cyber/ipa-decrypt-lab",
  "secret_name":secret,
  "key_id":keyID,
  "encrypted_value":base64.StdEncoding.EncodeToString(sealed),
 })
}

func main(){ if run()!=nil { fmt.Fprintln(os.Stderr,"model_sealing_failed"); os.Exit(2) } }
