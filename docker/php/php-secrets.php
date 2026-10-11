<?php
declare(strict_types=1);

// Only references enter the generated manifest. Values live in process memory.
function yia_secret(string $path): string
{
    if (!is_file($path) || !is_readable($path)) {
        throw new RuntimeException('secret_unavailable');
    }
    $value = @file_get_contents($path);
    if ($value === false || str_contains($value, "\0") || preg_match('//u', $value) !== 1) {
        throw new RuntimeException('invalid_secret');
    }
    $value = rtrim($value, "\n");
    if ($value === '') {
        throw new RuntimeException('empty_secret');
    }
    return $value;
}

function yia_manifest(string $path): array
{
    $content = @file_get_contents($path);
    if ($content === false) {
        throw new RuntimeException('manifest_unavailable');
    }
    return json_decode($content, true, 512, JSON_THROW_ON_ERROR);
}

function yia_application_environment(array $application): void
{
    foreach ($application['secret_files'] ?? [] as $variable => $path) {
        putenv($variable . '=' . yia_secret($path));
    }
}

function yia_fpm_environment(array $applications): void
{
    foreach ($applications as $name => $application) {
        foreach ($application['secret_files'] ?? [] as $variable => $path) {
            putenv('YIA_SECRET_' . bin2hex((string)$name) . '_' . $variable . '=' . yia_secret($path));
        }
    }
}

function yia_exec(array $command): never
{
    $binary = $command[0] ?? '';
    if (!str_contains($binary, '/')) {
        foreach (explode(':', getenv('PATH') ?: '/usr/local/bin:/usr/bin:/bin:/sbin') as $directory) {
            if (is_file($directory . '/' . $binary) && is_executable($directory . '/' . $binary)) {
                $binary = $directory . '/' . $binary;
                break;
            }
        }
    }
    @pcntl_exec($binary, array_slice($command, 1), getenv());
    throw new RuntimeException('exec_failed');
}

function yia_runtime_error(): never
{
    fwrite(STDERR, "{\"error\":{\"code\":\"YIA_CONFIG_INVALID\",\"message\":\"PHP runtime preparation failed (values omitted).\"}}\n");
    exit(2);
}

if (realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    try {
        $mode = $argv[1] ?? '';
        $applications = yia_manifest($argv[2] ?? '');
        if ($mode === 'fpm') {
            // fpm <manifest> <command...>; manifest is argument 2.
            yia_fpm_environment($applications);
            yia_exec(array_slice($argv, 3));
        }
        if ($mode !== 'exec' || !isset($applications[$argv[3] ?? ''])) {
            throw new RuntimeException('unknown_application');
        }
        $name = $argv[3];
        yia_application_environment($applications[$name]);
        if (!chdir('/workspace/' . $name)) {
            throw new RuntimeException('invalid_working_directory');
        }
        yia_exec(['/sbin/su-exec', 'yia', 'docker-php-entrypoint', ...array_slice($argv, 4)]);
    } catch (Throwable $error) {
        yia_runtime_error();
    }
}
