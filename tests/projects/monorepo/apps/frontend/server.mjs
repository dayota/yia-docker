import { createServer } from "node:http";

const arguments_ = process.argv.slice(2);

function option(name, fallback) {
  const index = arguments_.indexOf(name);
  return index >= 0 && arguments_[index + 1] ? arguments_[index + 1] : fallback;
}

const host = option("--host", "127.0.0.1");
const port = Number(option("--port", "3000"));

createServer((_request, response) => {
  response.writeHead(200, { "content-type": "text/plain" });
  response.end("Yia Node fixture: frontend\n");
}).listen(port, host);
