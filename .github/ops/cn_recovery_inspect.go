// Diagnostic-only extension to the pinned upstream recovery package.
// No alternative records, keys or identities are tried; no model is emitted.
package recovery

import (
 "context"
 "crypto/aes"
 "os"
 "time"
 "github.com/DrWhax/unfairplay/internal/recovery/tagengine"
)

type LabCNInspection struct {
 Schema string `json:"schema"`
 Status string `json:"status"`
 Stage string `json:"stage"`
 SIDBAuthenticated bool `json:"sidb_authenticated"`
 ExactRouteMatched bool `json:"exact_route_matched"`
 FirstBlockAccepted bool `json:"first_block_accepted"`
 FullLicenseAccepted bool `json:"full_license_accepted"`
 RegistryCount int `json:"registry_count"`
 RegistryRecords int `json:"registry_records"`
 TreeNodes int `json:"tree_nodes"`
 RootVersion uint32 `json:"root_version"`
 AccountVersion uint32 `json:"account_version"`
 TypeBytes int `json:"type_bytes"`
 SignBytes int `json:"sign_bytes"`
 ValueBytes int `json:"value_bytes"`
 ModelWritten bool `json:"model_written"`
}

func labCNInspectionBase() LabCNInspection {
 return LabCNInspection{Schema:"cn-offline-recovery-inspection-v1",Status:"input_rejected",Stage:"load_inputs"}
}

func LabCNInspect(sidbPath, sinfPath, hardwarePath string) LabCNInspection {
 report:=labCNInspectionBase()
 for _,p:=range []string{sidbPath,sinfPath,hardwarePath} {
  info,err:=os.Lstat(p)
  if err!=nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077!=0 || info.Size()<=0 || info.Size()>1048576 {return report}
 }
 inputs,err:=loadCurrentRecoveryInputs([]string{"SC Info.sidb="+sidbPath,"diagnostic.sinf="+sinfPath},hardwarePath)
 if err!=nil {return report};defer inputs.clear()
 report.Stage="decode_sidb";report.Status="sidb_rejected"
 registries,_,_,layout,err:=deriveCurrentSelectionRegistryCandidatesWithEvidence(inputs.files,inputs.hardware)
 if err!=nil {return report};defer clearDecodedSIDBRegistryCandidates(registries)
 report.SIDBAuthenticated=true;report.RegistryCount=len(registries);report.RegistryRecords=layout.RegistryRecords;report.TreeNodes=layout.TreeNodes
 report.Stage="select_route";report.Status="route_rejected"
 root,err:=nativeSIDBRootCursor(inputs.hardware);if err!=nil{return report}
 ctx,cancel:=context.WithTimeout(context.Background(),60*time.Second);defer cancel()
 book,err:=tagengine.GenerateCodebookWithContext(ctx,inputs.hardware);if err!=nil{return report};defer clear(book)
 codes:=make(map[uint32]string,len(book));defer clear(codes)
 for _,entry:=range book {
  if len(entry.Semantic)!=4{return report};if _,exists:=codes[entry.Raw];exists{return report};codes[entry.Raw]=entry.Semantic
 }
 decode:=func(raw uint32)(string,bool){tag,ok:=codes[raw];return tag,ok}
 return labCNInspectSelection(inputs.files["diagnostic.sinf"],registries,inputs.hardware,root,decode,report)
}

func labCNInspectSelection(sinf []byte,registries []decodedSIDBRegistryCandidate,hardware []byte,root int,decode sidbTagDecoder,report LabCNInspection) LabCNInspection {
 report.Stage="select_route";report.Status="route_rejected"
 if len(registries)!=1 || !registries[0].Registry.Tree || len(registries[0].Data)==0{return report}
 user,keyID,err:=enrollmentSINFSelector(sinf);if err!=nil{return report}
 route,err:=selectTaggedSIDBRoute(decode,sinf,registries[0].Data,root);if err!=nil{return report};defer clear(route.Window[:])
 if route.RecordIndex<0 || route.RecordIndex>=len(registries[0].Registry.Records) || registries[0].Registry.Records[route.RecordIndex]!=route.Record{return report}
 report.ExactRouteMatched=true;report.RootVersion=uint32(route.Version);report.AccountVersion=uint32(route.AccountVersion)
 report.TypeBytes=route.TypeLength;report.SignBytes=route.SignLength;report.ValueBytes=route.ValueLength
 report.Stage="derive_class_key";report.Status="class_derivation_rejected"
 key,err:=accountClassKey(hardware,user,keyID);if err!=nil{return report};defer clear(key[:])
 valu,err:=deriveClassValuWindow(route.Record,0);if err!=nil{return report};defer clear(valu[:])
 block,err:=aes.NewCipher(key[:]);if err!=nil{return report}
 var modelKey [16]byte;defer clear(modelKey[:]);block.Decrypt(modelKey[:],valu[:])
 probe,err:=newCurrentSINFModelKeyProbe(sinf);if err!=nil{return report}
 report.Stage="first_block";report.Status="first_block_rejected"
 accepted,err:=probe.accepts(modelKey);if err!=nil || !accepted{return report};report.FirstBlockAccepted=true
 var precursor [16]byte;defer clear(precursor[:]);for i:=range precursor{precursor[i]=applyCurrentFairPlayByteMask(modelKey[i])}
 report.Stage="full_license";report.Status="full_license_rejected"
 accepted,err=validateCurrentSINFPrecursor(sinf,precursor);if err!=nil || !accepted{return report}
 report.FullLicenseAccepted=true;report.Status="license_accepted_diagnostic_only";return report
}
