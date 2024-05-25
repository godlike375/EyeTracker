import dataclasses
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy

from tracker.abstractions import ID


class Commands(Enum):
    START_TRACKING = 1
    STOP_TRACK = 2
    START_CALIBRATION = 3


@dataclass
class Coordinates:
    x: int = 0
    y: int = 0


@dataclass
class BoundingBox:
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0


@dataclass
class ImageWithCoordinates:
    image: numpy.ndarray
    coords: list[BoundingBox] = dataclasses.field(default_factory=list)


class Packable:
    def pack(self) -> str:
        return json.dumps(self)

    @classmethod
    def unpack(cls, bytes) -> 'Packable':
        return json.loads(bytes)


@dataclass(slots=True, frozen=True)
class Command(Packable):
    type: Commands
    data: Optional[ID]
