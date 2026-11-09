package recovery
import (
 "encoding/binary"
 "encoding/json"
 "testing"
)
func TestLabCNInspectionExactValueAndPrivacy(t *testing.T){
 decode,_,body:=syntheticRoute();hardware:=[]byte{0,1,2,3,4,5}
 registry,err:=parseDecodedSIDBRegistry(body,2);if err!=nil{t.Fatal("fixture registry")}
 user:=uint32(0x12345678);user=user*0xa46fd0ff+0xfe063531;keyID:=uint32(7)
 key,err:=accountClassKey(hardware,user,keyID);if err!=nil{t.Fatal("fixture class")}
 index:=-1;for i,r:=range registry.Records{if r.SourceOffset==174{index=i}}
 if index<0{t.Fatal("fixture value")}
 precursor,err:=deriveCurrentSINFPrecursorFromRecordWindow(registry.Records[index],0,key);if err!=nil{t.Fatal("fixture precursor")}
 sinf:=syntheticCurrentSINFForPrecursor(t,precursor)
 start,end,err:=enrollmentAtom(sinf,0,len(sinf),"sinf");if err!=nil{t.Fatal("fixture root")}
 start,end,err=enrollmentAtom(sinf,start,end,"schi");if err!=nil{t.Fatal("fixture scheme")}
 p,_,err:=enrollmentAtom(sinf,start,end,"user");if err!=nil{t.Fatal("fixture user")};binary.BigEndian.PutUint32(sinf[p:],user)
 p,_,err=enrollmentAtom(sinf,start,end,"key ");if err!=nil{t.Fatal("fixture key")};binary.BigEndian.PutUint32(sinf[p:],keyID)
 regs:=[]decodedSIDBRegistryCandidate{{Registry:registry,Data:body}}
 report:=labCNInspectSelection(sinf,regs,hardware,2,decode,labCNInspectionBase())
 if !report.ExactRouteMatched || !report.FirstBlockAccepted || !report.FullLicenseAccepted || report.ModelWritten || report.Status!="license_accepted_diagnostic_only"{t.Fatal("positive diagnostic rejected")}
 encoded,err:=json.Marshal(report);if err!=nil{t.Fatal("schema")};var safe map[string]any;if json.Unmarshal(encoded,&safe)!=nil || len(safe)!=16{t.Fatal("unexpected public fields")}
 wrong:=append([]byte(nil),sinf...);priv,err:=currentSINFPrivateSource(wrong);if err!=nil{t.Fatal("fixture private record")};priv[0]^=0x80
 report=labCNInspectSelection(wrong,regs,hardware,2,decode,labCNInspectionBase())
 if !report.ExactRouteMatched || report.FirstBlockAccepted || report.FullLicenseAccepted || report.ModelWritten || report.Status!="first_block_rejected"{t.Fatal("first block diagnostic failed closed")}
 report=labCNInspectSelection(sinf,append(regs,regs...),hardware,2,decode,labCNInspectionBase())
 if report.ExactRouteMatched || report.ModelWritten || report.Status!="route_rejected"{t.Fatal("multiple registry accepted")}
}
func TestLabCNInspectionMissingInputIsSanitized(t *testing.T){
 report:=LabCNInspect("PRIVATE_PATH_NOT_PRESENT","PRIVATE_PATH_NOT_PRESENT","PRIVATE_PATH_NOT_PRESENT")
 if report.Status!="input_rejected" || report.ModelWritten{t.Fatal("missing input accepted")}
}
