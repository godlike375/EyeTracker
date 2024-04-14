import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from tracker.abstractions import Packable, ID
from tracker.image import CompressedImage


class Commands(Enum):
    START_TRACKING = 1
    STOP_TRACK = 2
    START_CALIBRATION = 3


@dataclass
class Coordinates:
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0

@dataclass
class StartTracking:
    coords: Coordinates
    frame_id: ID
    tracker_id: ID


@dataclass
class ImageWithCoordinates(Packable):
    image: CompressedImage
    coords: list[Coordinates] = dataclasses.field(default_factory=list)


@dataclass(slots=True, frozen=True)
class Command(Packable):
    type: Commands
    data: Optional[StartTracking | ID]
