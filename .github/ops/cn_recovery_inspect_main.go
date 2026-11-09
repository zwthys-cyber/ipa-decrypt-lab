package main
import (
 "encoding/json"
 "os"
 "github.com/DrWhax/unfairplay/internal/recovery"
)
func main(){
 if len(os.Args)!=4 || os.Getenv("GITHUB_ACTIONS")!="true" {os.Exit(2)}
 // Paths and errors never enter stdout; only this fixed diagnostic schema does.
 json.NewEncoder(os.Stdout).Encode(recovery.LabCNInspect(os.Args[1],os.Args[2],os.Args[3]))
}
