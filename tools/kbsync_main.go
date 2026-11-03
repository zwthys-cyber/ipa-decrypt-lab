package main

import (
    "context"
    "encoding/base64"
    "encoding/hex"
    "encoding/json"
    "errors"
    "io"
    "os"
    "strconv"
    "time"

    "github.com/majd/ipatool/v2/internal/sap/assets"
    "github.com/majd/ipatool/v2/internal/sap/machine"
)

func parse(r io.Reader) ([]byte, uint64, error) {
    var input struct { GUID string `json:"guid"`; DSID string `json:"dsid"` }
    decoder := json.NewDecoder(io.LimitReader(r, 1025))
    decoder.DisallowUnknownFields()
    if err := decoder.Decode(&input); err != nil { return nil, 0, err }
    var extra interface{}
    if decoder.Decode(&extra) != io.EOF { return nil, 0, errors.New("trailing input") }
    guid, err := hex.DecodeString(input.GUID)
    if err != nil || len(guid) != 6 { return nil, 0, errors.New("invalid guid") }
    dsid, err := strconv.ParseUint(input.DSID, 10, 64)
    if err != nil || dsid == 0 { return nil, 0, errors.New("invalid dsid") }
    return guid, dsid, nil
}

func execute() error {
    ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
    defer cancel()
    if len(os.Args) == 2 && os.Args[1] == "--prewarm" {
        _, err := assets.Load(ctx)
        return err
    }
    guid, dsid, err := parse(os.Stdin)
    if err != nil { return err }
    bundle, err := assets.Load(ctx)
    if err != nil { return err }
    blob, err := machine.GenerateKBSync(ctx, bundle, guid, dsid)
    if err != nil { return err }
    if len(blob) == 0 || len(blob) > 1024*1024 { return errors.New("invalid blob size") }
    _, err = io.WriteString(os.Stdout, base64.StdEncoding.EncodeToString(blob))
    return err
}

func main() {
    if os.Getenv("GITHUB_ACTIONS") != "true" && os.Getenv("LAB_KBSYNC_CHILD") != "1" { os.Exit(2) }
    if execute() != nil { os.Exit(1) }
}
