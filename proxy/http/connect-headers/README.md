# Demonstration of custom HTTP headers for HTTP CONNECT proxy request
You can find out how to send custom HTTP headers to the proxy server and read data from the headers of HTTP replies. Some programming languages have this feature in the standard library, and some require monkey patching.

* Golang >=1.20 standard library
* NodeJS standard library
* Python3 aiohttp and httpx(httpcore) requires patching

Be aware that the proxy server will send you a reply only for the CONNECT HTTP method, which is used to establish TUNNEL with the target resource. It's essential for the TLS protocol, but can be used for any TCP-powered protocol as well. If you use plain HTTP URLs from the target resource, your HTTP client will just send your requests w/o additional requests with the CONNECT method.
