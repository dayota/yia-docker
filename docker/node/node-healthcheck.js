"use strict";

const net = require("node:net");

const rawPort = process.env.YIA_NODE_PORT;

if (!rawPort) {
  try {
    process.kill(1, 0);
    process.exit(0);
  } catch {
    process.exit(1);
  }
}

const port = Number(rawPort);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  process.exit(1);
}

const socket = net.createConnection({ host: "127.0.0.1", port });
socket.setTimeout(2000);
socket.once("connect", () => {
  socket.destroy();
  process.exit(0);
});
socket.once("timeout", () => {
  socket.destroy();
  process.exit(1);
});
socket.once("error", () => process.exit(1));
