<?php
pcntl_async_signals(true);
pcntl_signal(SIGTERM, function (): void { exit(0); });
while (true) { usleep(100000); }
