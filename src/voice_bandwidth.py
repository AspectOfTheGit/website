from datetime import datetime, timezone

from src.config import (
    VOICE_ROOM_START_BITRATE_KBPS,
    VOICE_ROOM_MIN_BITRATE_KBPS,
    VOICE_ROOM_BANDWIDTH_LIMIT_BYTES,
    VOICE_ROOM_BANDWIDTH_DETERIORATION_THRESHOLD_RATIO,
)


class VoiceBandwidthController:
    """A single shared bandwidth controller for all voice rooms."""
    def __init__(
        self,
        limit_bytes,
        start_bitrate_kbps,
        min_bitrate_kbps,
        deterioration_threshold_ratio=0.5,
    ):
        self.limit_bytes = limit_bytes
        self.start_bitrate_kbps = start_bitrate_kbps
        self.min_bitrate_kbps = min_bitrate_kbps
        self.deterioration_threshold_ratio = max(0.0, min(1.0, deterioration_threshold_ratio))
        self.used_bytes = 0
        self._enabled = True
        self._last_reset_key = None

    def _reset_if_needed(self):
        now = datetime.now(timezone.utc)
        month_key = (now.year, now.month)
        if self._last_reset_key != month_key:
            self.used_bytes = 0
            self._enabled = True
            self._last_reset_key = month_key

    def record_bytes(self, byte_count):
        self._reset_if_needed()
        if byte_count <= 0:
            return self.get_state()

        self.used_bytes += byte_count
        self._enabled = self.used_bytes < self.limit_bytes
        return self.get_state()

    def is_enabled(self):
        self._reset_if_needed()
        return self._enabled and self.used_bytes < self.limit_bytes

    def get_quality_bitrate_kbps(self):
        self._reset_if_needed()
        if not self.is_enabled():
            return 0

        usage_ratio = self.used_bytes / self.limit_bytes if self.limit_bytes else 0
        if usage_ratio < self.deterioration_threshold_ratio:
            return self.start_bitrate_kbps

        if usage_ratio >= 1.0:
            return 0

        progress = (usage_ratio - self.deterioration_threshold_ratio) / (1.0 - self.deterioration_threshold_ratio)
        progress = max(0.0, min(1.0, progress))
        return max(
            self.min_bitrate_kbps,
            self.start_bitrate_kbps - int((self.start_bitrate_kbps - self.min_bitrate_kbps) * progress),
        )

    def get_state(self):
        self._reset_if_needed()
        bitrate = self.get_quality_bitrate_kbps()
        usage_ratio = self.used_bytes / self.limit_bytes if self.limit_bytes else 0
        return {
            "enabled": self.is_enabled(),
            "bitrate_kbps": bitrate,
            "used_bytes": self.used_bytes,
            "limit_bytes": self.limit_bytes,
            "remaining_bytes": max(0, self.limit_bytes - self.used_bytes),
            "usage_ratio": usage_ratio,
            "threshold_ratio": self.deterioration_threshold_ratio,
        }


# Shared across all voice rooms so usage in any room affects the global audio quality.
voice_bandwidth_controller = VoiceBandwidthController(
    limit_bytes=VOICE_ROOM_BANDWIDTH_LIMIT_BYTES,
    start_bitrate_kbps=VOICE_ROOM_START_BITRATE_KBPS,
    min_bitrate_kbps=VOICE_ROOM_MIN_BITRATE_KBPS,
    deterioration_threshold_ratio=VOICE_ROOM_BANDWIDTH_DETERIORATION_THRESHOLD_RATIO,
)


def get_voice_bandwidth_controller():
    return voice_bandwidth_controller
