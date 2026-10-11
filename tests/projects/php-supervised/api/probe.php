<?php
$socket = @stream_socket_client('tcp://127.0.0.1:8080', $errno, $error, .5);
if ($socket === false) { exit(1); }
fclose($socket);
