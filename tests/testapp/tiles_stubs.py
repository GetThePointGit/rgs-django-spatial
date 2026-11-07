"""Stub-storages voor tests van ``rgs_django_spatial.tiles.storage``.

Via ``STORAGES`` instelbaar (dotted path), dus geen netwerk of S3 nodig.
"""

from django.core.files.storage import Storage

# (naam, expires) per url_signed-aanroep; tests legen deze lijst zelf.
SIGNED_CALLS: list[tuple[str, int]] = []


class SignedStubStorage(Storage):
    """Storage mét ``url_signed``, zoals ``FsspecStorage`` op S3."""

    def url(self, name):
        return f"/plain/{name}"

    def url_signed(self, name, expires=3600, method="GET", response_headers=None):
        SIGNED_CALLS.append((name, expires))
        return f"https://signed.example/{name}?ttl={expires}"


class UnsignedStubStorage(SignedStubStorage):
    """Storage met ``url_signed`` die geen S3-backend heeft."""

    def url_signed(self, name, expires=3600, method="GET", response_headers=None):
        raise NotImplementedError("geen S3")
