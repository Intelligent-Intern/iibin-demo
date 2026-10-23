# iibin-demo

Local integration demo for the sibling `iibin-js` and `iibin-py` repositories.

The initial demo will send user-entered text as a schema-based IIBIN binary WebSocket frame to a Python server and decode the binary reply in the browser. It will display the request/response values, transferred byte counts and round-trip duration. An optional speech-generation extension can then demonstrate streamed binary audio.

Implementation and local execution are pending the native codec extraction, Python binding and JavaScript wire-format alignment. No successful interoperability test is claimed.
