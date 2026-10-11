<?php
// Synthetic protocol fixture, not an implementation or recipe for Reverb.
pcntl_async_signals(true);
pcntl_signal(SIGTERM, function (): void { exit(0); });
$server = stream_socket_server('tcp://0.0.0.0:8080', $errno, $error);
if ($server === false) { exit(1); }
while (true) {
    $client = @stream_socket_accept($server, 1);
    if ($client === false) { continue; }
    stream_set_timeout($client, 2);
    $line = fgets($client);
    if ($line === false) { fclose($client); continue; }
    $path = explode(' ', $line)[1] ?? '';
    $headers = [];
    while (($line = fgets($client)) !== false && trim($line) !== '') {
        [$key, $value] = array_pad(explode(':', $line, 2), 2, '');
        $headers[strtolower($key)] = trim($value);
    }
    if (($headers['origin'] ?? '') === 'https://forbidden.invalid') {
        fwrite($client, "HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
    } elseif (isset($headers['sec-websocket-key'])) {
        $accept = base64_encode(sha1($headers['sec-websocket-key'] . '258EAFA5-E914-47DA-95CA-C5AB0DC85B11', true));
        fwrite($client, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: $accept\r\n\r\n");
        fwrite($client, "\x81\x0fsynthetic-event");
    } elseif ($path === '/apps/slow') {
        sleep(3);
    } else {
        $body = json_encode(['path' => $path, 'host' => $headers['host'] ?? '', 'proto' => $headers['x-forwarded-proto'] ?? '']);
        fwrite($client, "HTTP/1.1 200 OK\r\nContent-Length: " . strlen($body) . "\r\nConnection: close\r\n\r\n" . $body);
    }
    fclose($client);
}
