from server.routes_binary import (
    _is_supported_upload_name,
    _looks_like_executable_binary,
    _sanitize_upload_filename,
)


def test_upload_name_allows_extensionless_and_known_binary_extensions() -> None:
    assert _is_supported_upload_name('recon')
    assert _is_supported_upload_name('recon.exe')
    assert _is_supported_upload_name('recon.bin')
    assert _is_supported_upload_name('recon.elf')
    assert _is_supported_upload_name('recon.appimage')


def test_upload_name_rejects_hidden_files_scripts_and_images() -> None:
    assert not _is_supported_upload_name('')
    assert not _is_supported_upload_name('.payload')
    assert not _is_supported_upload_name('agent.sh')
    assert not _is_supported_upload_name('payload.ps1')
    assert not _is_supported_upload_name('photo.png')


def test_upload_filename_is_sanitized_to_basename() -> None:
    assert _sanitize_upload_filename(r'C:\Users\me\recon.exe') == 'recon.exe'
    assert _sanitize_upload_filename('/tmp/recon') == 'recon'


def test_executable_magic_detects_pe_elf_and_macho() -> None:
    assert _looks_like_executable_binary(b'MZ\x90\x00')
    assert _looks_like_executable_binary(b'\x7fELF\x02\x01')
    assert _looks_like_executable_binary(b'\xcf\xfa\xed\xfe\x07\x00')
    assert not _looks_like_executable_binary(b'\x89PNG\r\n\x1a\n')
