const http = require("http");
const https = require("https");

const proxyURL = new URL('http://package-<PKG-ID>:<AUTH-KEY>@proxy.soax.com:5000');
const targetURL = new URL('https://checker.soax.com/api/ipinfo');
const base64EncCreds = Buffer.from(`${proxyURL.username}:${proxyURL.password}`).toString(
  "base64"
);

http
  .request({
    host: proxyURL.hostname,
    port: proxyURL.port,
    method: "CONNECT",
    path: targetURL.host, //host:port pair to create TUNNEL to 
    headers: {
      "Proxy-Authorization": `Basic ${base64EncCreds}`,
      "Respond-With": "uid,ip,country,region,city,isp", // You can add custom header if proxy support it. 
    },
  })
  .on("connect", (res, socket) => {
    console.log("-".repeat(80) + "\nProxy\n" + "-".repeat(80));
    console.log("*Headres*\n", res.headers);

    if (res.statusCode === 200) {
      // connected to proxy server
      https.get(
        {
          host: targetURL.hostname,
          socket: socket,
          agent: false,
          path: targetURL.pathname,
        },
        (res) => {
          console.log("-".repeat(80) + "\nTarget\n" + "-".repeat(80));
          console.log("*Headers*\n", JSON.stringify(res.headers, null, 2));
          let chunks = [];
          res.on("data", (chunk) => chunks.push(chunk));
          res.on("end", () => {
            payload = Buffer.concat(chunks).toString("utf8");
            payloadPP = JSON.stringify(JSON.parse(payload), null, 2);  
            console.log("*Payload*\n", payloadPP);
          });
        }
      );
    }
  })
  .on("error", (err) => {
    console.error("error", err);
  })
  .end();
