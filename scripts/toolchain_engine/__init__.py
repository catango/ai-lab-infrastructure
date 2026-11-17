"""Install engine for toolchain/manifest.toml (CR-2 design section 3). Standard library only.

One implementation of download, verification, extraction, and linking, used by Ansible, CI, and
verification. Nothing here uses a shell: commands are argument arrays.
"""
