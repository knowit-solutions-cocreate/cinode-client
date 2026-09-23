"""Resources: one class per segment of Cinode's URL tree.

The resource classes are reached through `Cinode`; only `UserRef` is public here.
"""

from cinode.resources._base import UserRef

__all__ = ["UserRef"]
