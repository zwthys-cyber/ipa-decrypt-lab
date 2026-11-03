package main
import ("strings"; "testing")
func TestParse(t *testing.T) {
    for _, input := range []string{
        `{"guid":"001122334455","dsid":"0"}`,
        `{"guid":"0011","dsid":"123"}`,
        `{"guid":"001122334455","dsid":"123","password":"secret"}`,
        `{"guid":"001122334455","dsid":"123"} {}`,
    } { if _, _, err := parse(strings.NewReader(input)); err == nil { t.Fatal("accepted invalid input") } }
    guid, dsid, err := parse(strings.NewReader(`{"guid":"001122334455","dsid":"123"}`))
    if err != nil || len(guid) != 6 || dsid != 123 { t.Fatal("valid input rejected") }
}
