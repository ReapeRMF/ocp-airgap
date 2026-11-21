# Print only the primary-key fingerprint from gpg --with-colons output.
# A subkey also has an fpr line. That line follows "sub", not "pub".
BEGIN { FS = ":" }
$1 == "pub" { want = 1; next }
$1 == "fpr" && want {
    print toupper($10)
    want = 0
    next
}
$1 == "sub" || $1 == "sec" || $1 == "ssb" { want = 0 }
