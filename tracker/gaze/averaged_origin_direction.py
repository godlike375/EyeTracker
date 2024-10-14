from tracker.utils.denoise import MovingAverageDenoiser3D


class AveragedEyeOriginDirection:
    def __init__(self, mean_count: int):
        self.origin: MovingAverageDenoiser3D = MovingAverageDenoiser3D(mean_count)
        self.direction: MovingAverageDenoiser3D = MovingAverageDenoiser3D(mean_count)

