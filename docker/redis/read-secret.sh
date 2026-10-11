#!/bin/sh

# Source this helper; output is captured by the caller, never logged.
yia_read_secret() {
    if [ ! -f "$1" ] || [ ! -r "$1" ]; then
        printf '%s\n' '{"error":{"code":"YIA_CONFIG_INVALID","message":"Secret file unavailable (values omitted)."}}' >&2
        return 2
    fi
    # Validate UTF-8 bytes without putting content in awk arguments or output.
    if ! od -An -v -t u1 "$1" 2>/dev/null | LC_ALL=C awk '
        { for (i=1; i<=NF; i++) {
            b=$i
            if (n>0) { if (b<lo || b>hi) exit 2; n--; lo=128; hi=191 }
            else if (b>=1 && b<=127) { }
            else if (b>=194 && b<=223) { n=1; lo=128; hi=191 }
            else if (b>=224 && b<=239) { n=2; lo=(b==224 ? 160 : 128); hi=(b==237 ? 159 : 191) }
            else if (b>=240 && b<=244) { n=3; lo=(b==240 ? 144 : 128); hi=(b==244 ? 143 : 191) }
            else exit 2
        }}
        END { if (n>0) exit 2 }
    '; then
        printf '%s\n' '{"error":{"code":"YIA_CONFIG_INVALID","message":"Secret must be UTF-8 without NUL (values omitted)."}}' >&2
        return 2
    fi
    yia_secret_value="$(cat "$1" 2>/dev/null)" || return 2
    if [ -z "$yia_secret_value" ]; then
        printf '%s\n' '{"error":{"code":"YIA_CONFIG_INVALID","message":"Secret must be non-empty (values omitted)."}}' >&2
        return 2
    fi
    printf '%s' "$yia_secret_value"
    unset yia_secret_value
}
