<?php
declare(strict_types=1);
require_once __DIR__ . '/php-secrets.php';

function yia_write_state(string $path, array $state): void
{
    $temporary = $path . '.' . getmypid();
    if (@file_put_contents($temporary, json_encode($state, JSON_THROW_ON_ERROR)) === false || !@rename($temporary, $path)) {
        throw new RuntimeException('state_write_failed');
    }
}

function yia_spawn(array $command, ?array $application, string $directory, bool $dropPrivileges): int
{
    $pid = pcntl_fork();
    if ($pid === -1) {
        throw new RuntimeException('fork_failed');
    }
    if ($pid === 0) {
        try {
            if (posix_setsid() === -1 || !chdir($directory)) {
                throw new RuntimeException('process_preparation_failed');
            }
            if ($application !== null) {
                yia_application_environment($application);
                if ($dropPrivileges) {
                    $command = ['/sbin/su-exec', 'yia', ...$command];
                }
            }
            yia_exec($command);
        } catch (Throwable $error) {
            yia_runtime_error();
        }
    }
    return $pid;
}

function yia_supervise(array $applications, array $fpm, string $stateDirectory, bool $dropPrivileges = true): int
{
    if (!is_dir($stateDirectory) && !@mkdir($stateDirectory, 0700, true)) {
        throw new RuntimeException('state_directory_failed');
    }
    $lock = fopen($stateDirectory . '/supervisor.lock', 'c');
    if ($lock === false || !flock($lock, LOCK_EX | LOCK_NB)) {
        throw new RuntimeException('supervisor_already_running');
    }
    $stopping = false;
    pcntl_async_signals(true);
    foreach ([SIGTERM, SIGINT, SIGQUIT] as $signal) {
        pcntl_signal($signal, function () use (&$stopping): void { $stopping = true; });
    }
    $state = ['started_at' => microtime(true), 'processes' => []];
    $children = [];
    // A dedicated child loads the namespaced FPM environment; the supervisor
    // and application children never inherit the other pools' secret values.
    $fpmPid = pcntl_fork();
    if ($fpmPid === -1) {
        throw new RuntimeException('fork_failed');
    }
    if ($fpmPid === 0) {
        try {
            posix_setsid();
            yia_fpm_environment($applications);
            yia_exec($fpm);
        } catch (Throwable $error) { yia_runtime_error(); }
    }
    $children['fpm'] = ['pid' => $fpmPid, 'grace' => 10, 'signal' => SIGQUIT];
    $state['processes']['fpm'] = ['pid' => $fpmPid, 'state' => 'running', 'exit_code' => null];
    try {
        foreach ($applications as $name => $application) {
            foreach ($application['processes'] ?? [] as $processName => $process) {
                $id = $name . '/' . $processName;
                $pid = yia_spawn($process['command'], $application, $process['working_directory'], $dropPrivileges);
                $children[$id] = ['pid' => $pid, 'grace' => $process['stop_grace_seconds'], 'signal' => SIGTERM];
                $state['processes'][$id] = ['pid' => $pid, 'state' => 'running', 'exit_code' => null];
            }
        }
        yia_write_state($stateDirectory . '/state.json', $state);
        $deadlines = [];
        while (true) {
            foreach ($children as $id => $child) {
                $wait = pcntl_waitpid($child['pid'], $status, WNOHANG);
                if ($wait === $child['pid']) {
                    $state['processes'][$id]['state'] = 'exited';
                    $state['processes'][$id]['exit_code'] = pcntl_wifexited($status) ? pcntl_wexitstatus($status) : 128 + pcntl_wtermsig($status);
                    unset($children[$id]);
                    yia_write_state($stateDirectory . '/state.json', $state);
                }
            }
            if ($stopping) {
                foreach ($children as $id => $child) {
                    if (!isset($deadlines[$id])) {
                        @posix_kill(-$child['pid'], $child['signal']);
                        @posix_kill($child['pid'], $child['signal']);
                        $deadlines[$id] = microtime(true) + $child['grace'];
                    } elseif (microtime(true) >= $deadlines[$id]) {
                        @posix_kill(-$child['pid'], SIGKILL);
                        @posix_kill($child['pid'], SIGKILL);
                    }
                }
                if (!$children) { break; }
            }
            // Exits remain observable; no child is ever automatically restarted.
            usleep(100000);
        }
    } finally {
        foreach ($children as $child) {
            @posix_kill(-$child['pid'], SIGKILL);
            @posix_kill($child['pid'], SIGKILL);
            pcntl_waitpid($child['pid'], $status);
        }
        flock($lock, LOCK_UN);
        fclose($lock);
    }
    return 0;
}

function yia_check_command(array $test, array $application, string $directory, float $timeout, bool $dropPrivileges): bool
{
    // A probe runner prevents values from becoming command arguments or logs.
    $pid = pcntl_fork();
    if ($pid === -1) { return false; }
    if ($pid === 0) {
        fclose(STDOUT);
        $stdout = fopen('/dev/null', 'w');
        fclose(STDERR);
        $stderr = fopen('/dev/null', 'w');
        try {
            posix_setsid();
            chdir($directory);
            yia_application_environment($application);
            yia_exec($dropPrivileges ? ['/sbin/su-exec', 'yia', ...$test] : $test);
        } catch (Throwable $error) { exit(2); }
    }
    $deadline = microtime(true) + $timeout;
    do {
        if (pcntl_waitpid($pid, $status, WNOHANG) === $pid) {
            return pcntl_wifexited($status) && pcntl_wexitstatus($status) === 0;
        }
        usleep(10000);
    } while (microtime(true) < $deadline);
    @posix_kill(-$pid, SIGKILL);
    @posix_kill($pid, SIGKILL);
    pcntl_waitpid($pid, $status);
    return false;
}

function yia_health(array $applications, string $stateDirectory, bool $dropPrivileges = true): bool
{
    $state = yia_manifest($stateDirectory . '/state.json');
    $expected = ['fpm'];
    foreach ($applications as $name => $application) {
        foreach ($application['processes'] ?? [] as $processName => $process) { $expected[] = $name . '/' . $processName; }
    }
    foreach ($expected as $id) {
        $process = $state['processes'][$id] ?? null;
        if ($process === null || $process['state'] !== 'running' || !@posix_kill($process['pid'], 0)) { return false; }
    }
    $cachePath = $stateDirectory . '/health.json';
    $cache = is_file($cachePath) ? yia_manifest($cachePath) : [];
    $healthy = true;
    foreach ($applications as $name => $application) {
        foreach ($application['processes'] ?? [] as $processName => $process) {
            if (!isset($process['healthcheck'])) { continue; }
            $health = $process['healthcheck'];
            $id = $name . '/' . $processName;
            $last = $cache[$id] ?? ['checked_at' => 0, 'failures' => 0, 'passed' => false];
            if (microtime(true) - $last['checked_at'] >= $health['interval']) {
                $passed = yia_check_command($health['test'], $application, $process['working_directory'], $health['timeout'], $dropPrivileges);
                $last['checked_at'] = microtime(true);
                $last['passed'] = $passed;
                $last['failures'] = $passed ? 0 : (microtime(true) - $state['started_at'] >= $health['start_period'] ? $last['failures'] + 1 : 0);
                $cache[$id] = $last;
            }
            // Never announce initial readiness before a successful probe.
            if (!$last['passed'] && ($last['failures'] >= $health['retries'] || !isset($last['ready']))) { $healthy = false; }
            if ($last['passed']) { $cache[$id]['ready'] = true; }
        }
    }
    yia_write_state($cachePath, $cache);
    return $healthy;
}

if (realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    try {
        $applications = yia_manifest($argv[2] ?? '');
        $mode = $argv[1] ?? '';
        if ($mode === 'run') { exit(yia_supervise($applications, ['docker-php-entrypoint', 'php-fpm'], '/run/yia-php')); }
        if ($mode === 'health') { exit(yia_health($applications, '/run/yia-php') ? 0 : 1); }
        if ($mode === 'status') {
            echo json_encode(yia_manifest('/run/yia-php/state.json')['processes'], JSON_THROW_ON_ERROR), "\n";
            exit(0);
        }
        throw new RuntimeException('invalid_mode');
    } catch (Throwable $error) { yia_runtime_error(); }
}
