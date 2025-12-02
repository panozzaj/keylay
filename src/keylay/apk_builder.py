"""APK building and signing for Android keyboard layouts."""

import hashlib
import io
import os
import zipfile
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

RESOURCES_DIR = Path(__file__).parent.parent.parent / "resources"

# Paths inside the APK for keyboard layout files
LAYOUT_PATH = "res/Q2.kcm"
LAYOUT2_PATH = "res/_f.kcm"


class ApkSigner:
    """Signs APK/JAR files using v1 (JAR) signing scheme."""

    def __init__(self, cert: x509.Certificate, private_key):
        self.cert = cert
        self.private_key = private_key

    @classmethod
    def from_pem_files(cls, cert_path: Path, key_path: Path, key_password: Optional[bytes] = None):
        """Load signing credentials from PEM files."""
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        private_key = serialization.load_pem_private_key(
            key_path.read_bytes(), password=key_password
        )
        return cls(cert, private_key)

    @classmethod
    def from_pkcs12(cls, p12_path: Path, password: bytes):
        """Load signing credentials from PKCS12 file."""
        private_key, cert, _ = pkcs12.load_key_and_certificates(p12_path.read_bytes(), password)
        return cls(cert, private_key)

    def _hash_file(self, data: bytes) -> str:
        """SHA-256 hash of file contents, base64 encoded."""
        import base64

        digest = hashlib.sha256(data).digest()
        return base64.b64encode(digest).decode("ascii")

    def _create_manifest(self, files: dict[str, bytes]) -> bytes:
        """Create MANIFEST.MF content."""
        lines = [
            "Manifest-Version: 1.0",
            "Created-By: keylay",
            "",
        ]
        for name, content in sorted(files.items()):
            digest = self._hash_file(content)
            lines.extend(
                [
                    f"Name: {name}",
                    f"SHA-256-Digest: {digest}",
                    "",
                ]
            )
        return "\r\n".join(lines).encode("utf-8")

    def _hash_manifest_section(self, name: str, digest: str) -> str:
        """Hash a single manifest entry section."""
        import base64

        section = f"Name: {name}\r\nSHA-256-Digest: {digest}\r\n\r\n"
        return base64.b64encode(hashlib.sha256(section.encode("utf-8")).digest()).decode("ascii")

    def _hash_manifest_main(self) -> str:
        """Hash the main attributes section of manifest."""
        import base64

        main = "Manifest-Version: 1.0\r\nCreated-By: keylay\r\n\r\n"
        return base64.b64encode(hashlib.sha256(main.encode("utf-8")).digest()).decode("ascii")

    def _create_signature_file(self, manifest: bytes, files: dict[str, bytes]) -> bytes:
        """Create .SF signature file content."""
        import base64

        manifest_hash = base64.b64encode(hashlib.sha256(manifest).digest()).decode("ascii")
        main_hash = self._hash_manifest_main()

        lines = [
            "Signature-Version: 1.0",
            "Created-By: keylay",
            f"SHA-256-Digest-Manifest: {manifest_hash}",
            f"SHA-256-Digest-Manifest-Main-Attributes: {main_hash}",
            "",
        ]

        for name, content in sorted(files.items()):
            file_digest = self._hash_file(content)
            section_digest = self._hash_manifest_section(name, file_digest)
            lines.extend(
                [
                    f"Name: {name}",
                    f"SHA-256-Digest: {section_digest}",
                    "",
                ]
            )

        return "\r\n".join(lines).encode("utf-8")

    def _create_pkcs7_signature(self, data: bytes) -> bytes:
        """Create PKCS#7 detached signature for APK v1 signing."""
        from cryptography.hazmat.primitives.serialization import pkcs7

        # NoCapabilities removes SMIMECapabilities which Android doesn't support
        signature = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(self.cert, self.private_key, hashes.SHA256())
            .sign(
                serialization.Encoding.DER,
                [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.NoCapabilities],
            )
        )
        return signature

    def sign_apk(
        self, input_zip: zipfile.ZipFile, output: io.BytesIO, replacements: dict[str, bytes]
    ):
        """
        Sign an APK with v1 (JAR) signing.

        Args:
            input_zip: Source APK as ZipFile
            output: BytesIO to write signed APK to
            replacements: Dict of path -> content for files to replace
        """
        files: dict[str, bytes] = {}

        # Collect all files, applying replacements
        for info in input_zip.infolist():
            if info.is_dir():
                continue
            name = info.filename
            # Skip existing signature files
            if name.startswith("META-INF/") and (
                name.endswith(".SF")
                or name.endswith(".RSA")
                or name.endswith(".DSA")
                or name.endswith(".EC")
                or name == "META-INF/MANIFEST.MF"
            ):
                continue

            if name in replacements:
                files[name] = replacements[name]
            else:
                files[name] = input_zip.read(name)

        # Create signature files
        manifest = self._create_manifest(files)
        sig_file = self._create_signature_file(manifest, files)
        pkcs7_sig = self._create_pkcs7_signature(sig_file)

        # Write signed APK
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as out_zip:
            # Write manifest and signatures first
            out_zip.writestr("META-INF/MANIFEST.MF", manifest)
            out_zip.writestr("META-INF/KEYLAY.SF", sig_file)
            out_zip.writestr("META-INF/KEYLAY.RSA", pkcs7_sig)

            # Write all other files
            for name, content in files.items():
                out_zip.writestr(name, content)


class ApkBuilder:
    """Builds keyboard layout APKs."""

    def __init__(self, signer: ApkSigner):
        self.signer = signer
        self._one_layout_apk: Optional[bytes] = None
        self._two_layout_apk: Optional[bytes] = None

    def init(self):
        """Load APK templates."""
        self._one_layout_apk = (RESOURCES_DIR / "app-oneLayout-release-unsigned.apk").read_bytes()
        self._two_layout_apk = (RESOURCES_DIR / "app-twoLayouts-release-unsigned.apk").read_bytes()

    def build_apk(self, layout: str, layout2: Optional[str] = None) -> bytes:
        """
        Build a signed APK with the given keyboard layout(s).

        Args:
            layout: Primary keyboard layout content (KCM format)
            layout2: Optional secondary layout content

        Returns:
            Signed APK bytes
        """
        if self._one_layout_apk is None:
            self.init()

        template = self._two_layout_apk if layout2 else self._one_layout_apk
        replacements = {LAYOUT_PATH: layout.encode("utf-8")}
        if layout2:
            replacements[LAYOUT2_PATH] = layout2.encode("utf-8")

        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(template), "r") as in_zip:
            self.signer.sign_apk(in_zip, output, replacements)

        return output.getvalue()


def create_builder_from_env() -> ApkBuilder:
    """Create an ApkBuilder using environment config or defaults."""
    key_password = os.environ.get("KEYLAY_KEY_PASSWORD", "exkeymo").encode()

    # Try PKCS12 first, then PEM files
    p12_path = RESOURCES_DIR / "keylay.p12"
    if p12_path.exists():
        signer = ApkSigner.from_pkcs12(p12_path, key_password)
    else:
        cert_path = RESOURCES_DIR / "keylay_cert.pem"
        key_path = RESOURCES_DIR / "keylay_key.pem"
        signer = ApkSigner.from_pem_files(cert_path, key_path)

    builder = ApkBuilder(signer)
    builder.init()
    return builder
