<?php
header('Content-Type: application/json');
echo json_encode(['fixture' => 'PHP fallback', 'secret_hash' => hash('sha256', getenv('DB_PASSWORD') ?: '')]);
