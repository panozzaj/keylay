"""Tests for APK building and signing."""

import io
import zipfile

import pytest

from keylay.apk_builder import ApkBuilder, ApkSigner, create_builder_from_env


@pytest.fixture
def builder():
    """Create a builder with test credentials."""
    return create_builder_from_env()


class TestApkBuilder:
    def test_build_single_layout(self, builder):
        layout = "type OVERLAY\nmap key 58 CTRL_LEFT\n"
        apk_bytes = builder.build_apk(layout)

        assert len(apk_bytes) > 0
        # Verify it's a valid ZIP
        with zipfile.ZipFile(io.BytesIO(apk_bytes)) as zf:
            names = zf.namelist()
            # Check for signature files
            assert "META-INF/MANIFEST.MF" in names
            assert "META-INF/KEYLAY.SF" in names
            assert "META-INF/KEYLAY.RSA" in names
            # Check layout was included
            assert "res/Q2.kcm" in names
            # Verify layout content
            kcm_content = zf.read("res/Q2.kcm").decode("utf-8")
            assert "map key 58 CTRL_LEFT" in kcm_content

    def test_build_dual_layout(self, builder):
        layout1 = "type OVERLAY\nmap key 58 CTRL_LEFT\n"
        layout2 = "type OVERLAY\nmap key 58 ESC\n"
        apk_bytes = builder.build_apk(layout1, layout2)

        with zipfile.ZipFile(io.BytesIO(apk_bytes)) as zf:
            names = zf.namelist()
            assert "res/Q2.kcm" in names
            assert "res/_f.kcm" in names

            kcm1 = zf.read("res/Q2.kcm").decode("utf-8")
            kcm2 = zf.read("res/_f.kcm").decode("utf-8")
            assert "CTRL_LEFT" in kcm1
            assert "ESC" in kcm2


class TestApkSigner:
    def test_manifest_creation(self, builder):
        """Test that manifest contains proper digests."""
        layout = "type OVERLAY\n"
        apk_bytes = builder.build_apk(layout)

        with zipfile.ZipFile(io.BytesIO(apk_bytes)) as zf:
            manifest = zf.read("META-INF/MANIFEST.MF").decode("utf-8")
            assert "Manifest-Version: 1.0" in manifest
            assert "SHA-256-Digest:" in manifest

    def test_signature_file_creation(self, builder):
        """Test that signature file is properly formatted."""
        layout = "type OVERLAY\n"
        apk_bytes = builder.build_apk(layout)

        with zipfile.ZipFile(io.BytesIO(apk_bytes)) as zf:
            sf = zf.read("META-INF/KEYLAY.SF").decode("utf-8")
            assert "Signature-Version: 1.0" in sf
            assert "SHA-256-Digest-Manifest:" in sf

    def test_pkcs7_signature_exists(self, builder):
        """Test that PKCS7 signature is created."""
        layout = "type OVERLAY\n"
        apk_bytes = builder.build_apk(layout)

        with zipfile.ZipFile(io.BytesIO(apk_bytes)) as zf:
            rsa = zf.read("META-INF/KEYLAY.RSA")
            # PKCS7 signatures start with specific ASN.1 header
            assert len(rsa) > 100
