package main

import (
    "fmt"
    "strings"
    "context"
	"encoding/json"
    "io/ioutil"
    "net/http"
    "net/url"
)

var PROXYURL = "http://package-<PKG-ID>:<AUTH-KEY>@proxy.soax.com:5000";
var TARGETURL = "https://checker.soax.com/api/ipinfo";

func pp(obj interface{}) {
	bytes, _ := json.MarshalIndent(obj, "", "  ")
	fmt.Println(string(bytes))
}

func main() {
    var proxyRespHeader http.Header
	var resp *http.Response
	var err error
    proxyURL, _ := url.Parse(PROXYURL)
    req, _ := http.NewRequest("GET", TARGETURL, nil)
    transport := http.Transport{
        Proxy:                 http.ProxyURL(proxyURL),
		GetProxyConnectHeader: func(ctx context.Context, proxyURL *url.URL, target string) (http.Header, error) {
            return http.Header{"Respond-With": []string{"uid,ip,country,region,city,isp"}}, nil
        },
        OnProxyConnectResponse: func(_ context.Context, _ *url.URL, connectReq *http.Request, connectRes *http.Response) error {
			// Require Golang >=1.20
            proxyRespHeader = connectRes.Header
            return nil
        },
    }
    if resp, err = transport.RoundTrip(req); err != nil {
        fmt.Printf("Error %s", err)
        return
    }

    defer resp.Body.Close()
    body, err := ioutil.ReadAll(resp.Body)
	var jsonMap map[string]interface{}
	var bodyPP string
    if err = json.Unmarshal([]byte(body), &jsonMap) ; err != nil {
	    bodyPP = string(body)
	} else {
		bytes, _ := json.MarshalIndent(jsonMap, "", "  ")
		bodyPP = string(bytes)
	}

    fmt.Printf(strings.Repeat("-", 80))
	fmt.Printf("\nProxy\n")
    fmt.Printf(strings.Repeat("-", 80))
	fmt.Printf("\n*headers*\n")
	pp(proxyRespHeader)

    fmt.Printf(strings.Repeat("-", 80))
	fmt.Printf("\nTarget\n")
    fmt.Printf(strings.Repeat("-", 80))
	fmt.Printf("\n*headers*\n")
	pp(resp.Header)
    fmt.Printf("\n*payload*\n%s\n", bodyPP)
}
